import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    user_id: Optional[int] = None
    name: str = ""
    email: str = ""
    phone: str = ""
    password_hash: str = ""
    created_at: Optional[datetime] = None

    @property
    def name_formatted(self) -> str:
        return self.name.strip().title()

    @property
    def email_normalized(self) -> str:
        return self.email.strip().lower()

    def validate(self) -> bool:
        if not self._validate_name(self.name):
            raise ValueError("Invalid name: must be 2-50 characters, letters and spaces only")
        if not self._validate_email(self.email):
            raise ValueError("Invalid email format")
        if not self._validate_phone(self.phone):
            raise ValueError("Invalid phone: must be 10 digits")
        if len(self.password_hash) < 8:
            raise ValueError("Password must be at least 8 characters")
        return True

    @staticmethod
    def _validate_name(name: str) -> bool:
        pattern = r"^[a-zA-Z\s]{2,50}$"
        return bool(re.match(pattern, name))

    @staticmethod
    def _validate_email(email: str) -> bool:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def _validate_phone(phone: str) -> bool:
        pattern = r"^\d{10}$"
        return bool(re.match(pattern, phone))


@dataclass
class Account:
    account_id: Optional[int] = None
    user_id: int = 0
    account_type: str = "Savings"
    balance: float = 0.0
    created_at: Optional[datetime] = None
    is_active: bool = True
    account_number: str = ""

    @property
    def formatted_balance(self) -> str:
        return f"₹{self.balance:,.2f}"

    @property
    def account_number_formatted(self) -> str:
        if not self.account_number:
            return "N/A"
        return f"****{self.account_number[-4:]}"

    def validate(self) -> bool:
        valid_types = {"Savings", "Current", "Fixed Deposit"}
        if self.account_type not in valid_types:
            raise ValueError(f"Invalid account type. Must be one of: {valid_types}")
        if self.balance < 0:
            raise ValueError("Balance cannot be negative")
        if not re.match(r"^\d{12}$", self.account_number):
            raise ValueError("Account number must be 12 digits")
        return True


@dataclass
class Transaction:
    transaction_id: Optional[int] = None
    account_id: int = 0
    transaction_type: str = ""
    amount: float = 0.0
    timestamp: Optional[datetime] = None
    description: str = ""
    status: str = "COMPLETED"
    related_account_id: Optional[int] = None

    @property
    def formatted_amount(self) -> str:
        return f"₹{self.amount:,.2f}"

    @property
    def formatted_timestamp(self) -> str:
        if not self.timestamp:
            return "N/A"
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def validate(self) -> bool:
        valid_types = {"DEPOSIT", "WITHDRAWAL", "TRANSFER", "INTEREST"}
        valid_statuses = {"PENDING", "COMPLETED", "FAILED", "REVERSED"}
        
        if self.transaction_type not in valid_types:
            raise ValueError(f"Invalid transaction type: {self.transaction_type}")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}")
        if self.amount <= 0:
            raise ValueError("Transaction amount must be positive")
        return True


class OTP:
    def __init__(self, otp_code: str, user_email: str, expires_at: datetime):
        self.otp_code = otp_code
        self.user_email = user_email
        self.expires_at = expires_at
        self.attempts = 0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @property
    def attempts_remaining(self) -> int:
        return max(0, 3 - self.attempts)

    def is_valid(self, code: str) -> bool:
        if self.is_expired:
            raise ValueError("OTP has expired")
        if self.attempts >= 3:
            raise ValueError("Maximum OTP attempts exceeded")
        return self.otp_code == code


class AccountStatistics:
    def __init__(self, total_balance: float = 0, total_deposits: float = 0,
                 total_withdrawals: float = 0, total_transfers: float = 0,
                 account_count: int = 0, transaction_count: int = 0):
        self.total_balance = total_balance
        self.total_deposits = total_deposits
        self.total_withdrawals = total_withdrawals
        self.total_transfers = total_transfers
        self.account_count = account_count
        self.transaction_count = transaction_count

    def to_dict(self) -> dict:
        return {
            "Total Balance": f"₹{self.total_balance:,.2f}",
            "Total Deposits": f"₹{self.total_deposits:,.2f}",
            "Total Withdrawals": f"₹{self.total_withdrawals:,.2f}",
            "Total Transfers": f"₹{self.total_transfers:,.2f}",
            "Accounts": self.account_count,
            "Transactions": self.transaction_count
        }
