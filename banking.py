from datetime import datetime, timedelta
from typing import List, Optional, Callable, Dict
from functools import reduce
from database import Database
from schemas import Account, Transaction, AccountStatistics


ACCOUNT_CONFIG = {
    "Savings": {"interest_rate": 0.04, "min_balance": 0},
    "Current": {"interest_rate": 0.0, "min_balance": 0},
    "Fixed Deposit": {"interest_rate": 0.07, "maturity_months": 12}
}

ALLOWED_ACCOUNT_TYPES = {"Savings", "Current", "Fixed Deposit"}
TRANSACTION_CATEGORIES = {"DEPOSIT", "WITHDRAWAL", "TRANSFER", "INTEREST"}


def create_interest_calculator(rate: float) -> Callable:
    def calculate(balance: float, days: int = 365) -> float:
        daily_rate = rate / 365
        return balance * daily_rate * days
    return calculate


class BankingManager:
    def __init__(self, db: Database):
        self.db = db

    def create_account(self, user_id: int, account_type: str) -> tuple[bool, str]:
        try:
            if account_type not in ALLOWED_ACCOUNT_TYPES:
                return False, f"Invalid account type. Must be one of: {ALLOWED_ACCOUNT_TYPES}"
            
            account_number = self._generate_account_number()
            
            account_id = self.db.execute_insert(
                """INSERT INTO accounts (user_id, account_type, account_number, balance)
                   VALUES (?, ?, ?, ?)""",
                (user_id, account_type, account_number, 0.0)
            )
            
            return True, f"Account created successfully. Account ID: {account_id}"
        except Exception as e:
            return False, str(e)

    def deposit(self, account_id: int, amount: float, description: str = "") -> tuple[bool, str]:
        try:
            if amount <= 0:
                return False, "Deposit amount must be positive"
            
            account = self._get_account(account_id)
            if not account:
                return False, "Account not found"
            if not account['is_active']:
                return False, "Account is inactive"
            
            new_balance = account['balance'] + amount
            
            self.db.execute_update(
                "UPDATE accounts SET balance = ? WHERE account_id = ?",
                (new_balance, account_id)
            )
            
            self.db.execute_insert(
                """INSERT INTO transactions 
                   (account_id, transaction_type, amount, description, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, "DEPOSIT", amount, description, "COMPLETED")
            )
            
            return True, f"Deposit successful. New balance: ₹{new_balance:,.2f}"
        except Exception as e:
            return False, str(e)

    def withdraw(self, account_id: int, amount: float, description: str = "") -> tuple[bool, str]:
        try:
            if amount <= 0:
                return False, "Withdrawal amount must be positive"
            
            account = self._get_account(account_id)
            if not account:
                return False, "Account not found"
            if not account['is_active']:
                return False, "Account is inactive"
            if account['balance'] < amount:
                return False, f"Insufficient balance. Available: ₹{account['balance']:,.2f}"
            
            new_balance = account['balance'] - amount
            
            self.db.execute_update(
                "UPDATE accounts SET balance = ? WHERE account_id = ?",
                (new_balance, account_id)
            )
            
            self.db.execute_insert(
                """INSERT INTO transactions
                   (account_id, transaction_type, amount, description, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, "WITHDRAWAL", amount, description, "COMPLETED")
            )
            
            return True, f"Withdrawal successful. New balance: ₹{new_balance:,.2f}"
        except Exception as e:
            return False, str(e)

    def transfer(self, from_account_id: int, to_account_id: int, 
                amount: float, description: str = "") -> tuple[bool, str]:
        try:
            if from_account_id == to_account_id:
                return False, "Cannot transfer to the same account"
            if amount <= 0:
                return False, "Transfer amount must be positive"
            
            from_account = self._get_account(from_account_id)
            to_account = self._get_account(to_account_id)
            
            if not from_account or not to_account:
                return False, "One or both accounts not found"
            if not from_account['is_active'] or not to_account['is_active']:
                return False, "One or both accounts are inactive"
            if from_account['balance'] < amount:
                return False, f"Insufficient balance. Available: ₹{from_account['balance']:,.2f}"
            
            queries = [
                ("UPDATE accounts SET balance = ? WHERE account_id = ?",
                 (from_account['balance'] - amount, from_account_id)),
                ("UPDATE accounts SET balance = ? WHERE account_id = ?",
                 (to_account['balance'] + amount, to_account_id)),
                ("""INSERT INTO transactions 
                    (account_id, transaction_type, amount, description, status, related_account_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (from_account_id, "TRANSFER", amount, f"Transfer to {to_account_id}: {description}", "COMPLETED", to_account_id)),
                ("""INSERT INTO transactions
                    (account_id, transaction_type, amount, description, status, related_account_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (to_account_id, "TRANSFER", amount, f"Transfer from {from_account_id}: {description}", "COMPLETED", from_account_id))
            ]
            
            self.db.execute_transaction(queries)
            
            return True, f"Transfer successful. ₹{amount:,.2f} transferred"
        except Exception as e:
            return False, str(e)

    def get_balance(self, account_id: int) -> Optional[float]:
        account = self._get_account(account_id)
        return account['balance'] if account else None

    def get_accounts(self, user_id: int) -> List[Dict]:
        result = self.db.execute_query(
            """SELECT account_id, account_type, account_number, balance, created_at, is_active
               FROM accounts WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,)
        )
        return [dict(row) for row in result]

    def get_transactions(self, account_id: int, limit: int = 50) -> List[Dict]:
        result = self.db.execute_query(
            """SELECT transaction_id, account_id, transaction_type, amount, timestamp, description, status
               FROM transactions WHERE account_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (account_id, limit)
        )
        return [dict(row) for row in result]

    def get_account_statistics(self, user_id: int) -> AccountStatistics:
        accounts = self.get_accounts(user_id)
        account_ids = [acc['account_id'] for acc in accounts]
        
        if not account_ids:
            return AccountStatistics()
        
        placeholders = ','.join('?' * len(account_ids))
        transactions = self.db.execute_query(
            f"""SELECT transaction_type, amount FROM transactions
                WHERE account_id IN ({placeholders})""",
            tuple(account_ids)
        )
        
        total_balance = sum(acc['balance'] for acc in accounts)
        
        deposit_filter = filter(lambda t: t['transaction_type'] == 'DEPOSIT', transactions)
        total_deposits = reduce(lambda acc, t: acc + t['amount'], deposit_filter, 0)
        
        withdrawal_filter = filter(lambda t: t['transaction_type'] == 'WITHDRAWAL', transactions)
        total_withdrawals = reduce(lambda acc, t: acc + t['amount'], withdrawal_filter, 0)
        
        transfer_filter = filter(lambda t: t['transaction_type'] == 'TRANSFER', transactions)
        total_transfers = reduce(lambda acc, t: acc + t['amount'], transfer_filter, 0)
        
        return AccountStatistics(
            total_balance=total_balance,
            total_deposits=total_deposits,
            total_withdrawals=total_withdrawals,
            total_transfers=total_transfers,
            account_count=len(accounts),
            transaction_count=len(transactions)
        )

    def calculate_interest(self, account_id: int) -> Optional[float]:
        account = self._get_account(account_id)
        if not account:
            return None
        
        account_type = account['account_type']
        if account_type not in ACCOUNT_CONFIG:
            return 0
        
        rate = ACCOUNT_CONFIG[account_type]['interest_rate']
        calculator = create_interest_calculator(rate)
        
        return calculator(account['balance'])

    def apply_interest(self, account_id: int) -> tuple[bool, str]:
        try:
            interest = self.calculate_interest(account_id)
            if interest is None or interest <= 0:
                return False, "No interest to apply"
            
            return self.deposit(account_id, interest, "Interest credited")
        except Exception as e:
            return False, str(e)

    def close_account(self, account_id: int) -> tuple[bool, str]:
        try:
            account = self._get_account(account_id)
            if not account:
                return False, "Account not found"
            if account['balance'] != 0:
                return False, "Cannot close account with non-zero balance"
            
            self.db.execute_update(
                "UPDATE accounts SET is_active = 0 WHERE account_id = ?",
                (account_id,)
            )
            
            return True, "Account closed successfully"
        except Exception as e:
            return False, str(e)

    def transaction_generator(self, account_id: int):
        """Generator: yields transactions one by one for memory efficiency"""
        transactions = self.get_transactions(account_id, limit=1000)
        for transaction in transactions:
            yield transaction

    def _get_account(self, account_id: int) -> Optional[Dict]:
        result = self.db.execute_query(
            "SELECT * FROM accounts WHERE account_id = ?",
            (account_id,)
        )
        return dict(result[0]) if result else None

    def _generate_account_number(self) -> str:
        import secrets
        return ''.join([str(secrets.randbelow(10)) for _ in range(12)])
