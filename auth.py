import hashlib
import secrets
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, Tuple
from functools import wraps
import re
import os
from dotenv import load_dotenv

load_dotenv()

from database import Database
from schemas import User, OTP


class PasswordManager:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return f"{salt}${pwd_hash.hex()}"

    @staticmethod
    def verify_password(password: str, hash_value: str) -> bool:
        try:
            salt, pwd_hash = hash_value.split('$')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            return new_hash.hex() == pwd_hash
        except ValueError:
            return False


class JWTManager:
    def __init__(self, secret: str = "banking_app_secret_key_demo"):
        self.secret = secret
        self.algorithm = "HS256"

    def generate_token(self, user_id: int, email: str, 
                      expires_in_hours: int = 24) -> str:
        header = {"alg": self.algorithm, "typ": "JWT"}
        payload = {
            "user_id": user_id,
            "email": email,
            "iat": datetime.now().isoformat(),
            "exp": (datetime.now() + timedelta(hours=expires_in_hours)).isoformat()
        }
        
        import base64
        header_b64 = base64.b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        message = f"{header_b64}.{payload_b64}"
        signature = hashlib.sha256(
            f"{message}{self.secret}".encode()
        ).hexdigest()
        
        return f"{message}.{signature}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            import base64
            payload_b64 = parts[1]
            padding = '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(
                base64.b64decode(payload_b64 + padding).decode()
            )
            
            exp_time = datetime.fromisoformat(payload.get('exp', ''))
            if datetime.now() > exp_time:
                return None
            
            return payload
        except Exception:
            return None


class OTPManager:
    def __init__(self, db: Database, expiry_minutes: int = 2):
        self.db = db
        self.expiry_minutes = expiry_minutes
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')

    def _send_email(self, recipient_email: str, subject: str, body: str) -> bool:
        """Send email via SMTP"""
        try:
            # Check if SMTP credentials are configured
            if not all([self.smtp_server, self.sender_email, self.sender_password]):
                print("⚠️  SMTP not configured. OTP not sent via email.")
                print("   Configure .env file with: SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD")
                return False
            
            message = MIMEText(body)
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = recipient_email
            
            # Connect and send
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(message)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False

    def generate_otp(self, email: str) -> str:
        """Generate OTP and send via email"""
        otp_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        expires_at = datetime.now() + timedelta(minutes=self.expiry_minutes)
        
        # Store in database
        self.db.execute_insert(
            "INSERT INTO otp (email, otp_code, expires_at) VALUES (?, ?, ?)",
            (email, otp_code, expires_at)
        )
        
        # Send via email
        subject = "Banking App - OTP Verification"
        body = f"""
Hello,

Your Banking Application OTP is: {otp_code}

This OTP will expire in {self.expiry_minutes} minutes.
Do not share this OTP with anyone.

If you didn't request this OTP, please ignore this email.

Best regards,
Banking Application Team
        """
        
        email_sent = self._send_email(email, subject, body)
        
        if email_sent:
            print(f"✅ OTP sent to {email}")
        else:
            print(f"⚠️  OTP generated but not sent (SMTP not configured)")
            print(f"   OTP for testing: {otp_code}")
        
        return otp_code

    def verify_otp(self, email: str, otp_code: str) -> bool:
        result = self.db.execute_query(
            """SELECT * FROM otp WHERE email = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (email,)
        )
        
        if not result:
            raise ValueError("No OTP found for this email")
        
        otp_record = result[0]
        expires_at = datetime.fromisoformat(otp_record['expires_at'])
        
        if datetime.now() > expires_at:
            raise ValueError("OTP has expired")
        
        if otp_record['otp_code'] != otp_code:
            raise ValueError("Invalid OTP")
        
        return True

    def cleanup_expired_otps(self):
        self.db.execute_update(
            "DELETE FROM otp WHERE expires_at < ?",
            (datetime.now(),)
        )


class AuthenticationManager:
    def __init__(self, db: Database):
        self.db = db
        self.password_manager = PasswordManager()
        self.jwt_manager = JWTManager()
        self.otp_manager = OTPManager(db)

    def signup(self, name: str, email: str, phone: str, password: str) -> Tuple[bool, str]:
        try:
            user = User(name=name, email=email, phone=phone, 
                       password_hash=password)
            user.validate()
            
            existing = self.db.execute_query(
                "SELECT user_id FROM users WHERE email = ?",
                (email,)
            )
            
            if existing:
                return False, "Email already registered"
            
            password_hash = self.password_manager.hash_password(password)
            user_id = self.db.execute_insert(
                """INSERT INTO users (name, email, phone, password_hash) 
                   VALUES (?, ?, ?, ?)""",
                (user.name_formatted, user.email_normalized, phone, password_hash)
            )
            
            return True, f"Signup successful. User ID: {user_id}"
        except ValueError as e:
            return False, str(e)

    def login(self, email: str, password: str) -> Tuple[bool, Optional[str], Optional[int]]:
        try:
            result = self.db.execute_query(
                "SELECT user_id, password_hash FROM users WHERE email = ?",
                (email.lower(),)
            )
            
            if not result:
                return False, "User not found", None
            
            user_record = result[0]
            if not self.password_manager.verify_password(password, 
                                                         user_record['password_hash']):
                return False, "Invalid password", None
            
            return True, "Login successful", user_record['user_id']
        except Exception as e:
            return False, str(e), None

    def generate_jwt(self, user_id: int, email: str) -> str:
        return self.jwt_manager.generate_token(user_id, email)

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        return self.jwt_manager.verify_token(token)

    def generate_otp_for_email(self, email: str) -> str:
        return self.otp_manager.generate_otp(email)

    def verify_otp_for_email(self, email: str, otp_code: str) -> bool:
        return self.otp_manager.verify_otp(email, otp_code)


def login_required(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        import streamlit as st
        
        if 'user_id' not in st.session_state or not st.session_state.user_id:
            st.error("You must be logged in to access this feature")
            st.stop()
        
        return func(*args, **kwargs)
    
    return wrapper


def admin_required(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        import streamlit as st
        
        if 'user_id' not in st.session_state or not st.session_state.user_id:
            st.error("You must be logged in to access this feature")
            st.stop()
        
        return func(*args, **kwargs)
    
    return wrapper