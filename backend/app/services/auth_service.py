from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

SECRET_KEY = os.getenv("SECRET_KEY", "leadpilot_secret_key_super_long_2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(password: str) -> str:
    # Tronquer le mot de passe à 72 bytes pour bcrypt
    password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    plain = plain[:72]
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])