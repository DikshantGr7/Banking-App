import csv
import json
from datetime import datetime
from typing import List, Dict, Any
import logging
from pathlib import Path


class Logger:
    def __init__(self, log_file: str = "banking_app.log"):
        self.log_file = log_file
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)

    def warning(self, message: str):
        self.logger.warning(message)


class TransactionExporter:
    @staticmethod
    def export_to_csv(transactions: List[Dict[str, Any]], 
                     filename: str = "transactions.csv") -> bool:
        try:
            if not transactions:
                return False
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(transactions[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(transactions)
            
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False

    @staticmethod
    def export_to_json(transactions: List[Dict[str, Any]],
                      filename: str = "transactions.json") -> bool:
        try:
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(transactions, jsonfile, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False


class AccountExporter:
    @staticmethod
    def export_account_info(account: Dict[str, Any],
                           transactions: List[Dict[str, Any]],
                           filename: str = "account_info.json") -> bool:
        try:
            export_data = {
                "account_info": account,
                "transactions": transactions,
                "export_date": datetime.now().isoformat()
            }
            
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"Error exporting account info: {e}")
            return False


class FormatHelper:
    @staticmethod
    def format_amount(amount: float) -> str:
        return f"₹{amount:,.2f}"

    @staticmethod
    def format_date(date_obj: Any) -> str:
        if isinstance(date_obj, str):
            return date_obj
        if isinstance(date_obj, datetime):
            return date_obj.strftime("%Y-%m-%d %H:%M:%S")
        return str(date_obj)

    @staticmethod
    def format_account_number(account_number: str) -> str:
        if not account_number or len(account_number) < 4:
            return "N/A"
        return f"****{account_number[-4:]}"

    @staticmethod
    def truncate_description(description: str, max_length: int = 50) -> str:
        if len(description) > max_length:
            return f"{description[:max_length-3]}..."
        return description


class ValidationHelper:
    @staticmethod
    def is_valid_amount(amount: float) -> bool:
        try:
            return isinstance(amount, (int, float)) and amount > 0
        except:
            return False

    @staticmethod
    def is_valid_email(email: str) -> bool:
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        import re
        pattern = r"^\d{10}$"
        return bool(re.match(pattern, phone))


logger = Logger()
