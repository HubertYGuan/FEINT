from typing import Optional, Annotated

from datetime import datetime, timedelta, timezone

from enum import Enum

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.security import (
  HTTPAuthorizationCredentials,
  HTTPBearer,
  HTTPBasic,
  HTTPBasicCredentials
)

from pydantic import BaseModel, EmailStr

from pyotp import TOTP
import pyotp
from databaseinit import Get_Users
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, insert, update
from db_models.user_models import User_DB

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="../.env")
SUPER_SECRET_KEY = os.getenv('SUPER_SECRET_KEY')
class ErrorCode(Enum):
  SUCCESS = 0
  OTP_REQUIRED = 1
  INVALID_OTP = 2
  INVALID_CREDENTIALS = 3

class User(BaseModel):
  username: str
  email: Optional[EmailStr] = None
  full_name: Optional[str] = None
  disabled: Optional[bool]
  hashed_password: str
  secret_key: str
  otp_enabled: bool

class Login(BaseModel):
  user: Optional[User] = None
  status: ErrorCode

class Login_Response(BaseModel):
  token: Optional[str] = None
  status: ErrorCode

class Token(BaseModel):
  access_token: str
  token_type: str

class TokenData(BaseModel):
  username: Optional[str] = None

basic_security = HTTPBasic()
bearer_security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
  return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
  return pwd_context.verify(plain_password, hashed_password)

# Data is JWT code and username, default expiration is 15 minutes
async def create_jwt(data: dict, users: AsyncSession, expires_delta: Optional[timedelta] = None) -> str:
  to_encode = data.copy()
  result = await users.execute(select(User_DB).filter(User_DB.username == data["sub"]))
  user = result.scalars().first()

  if not user:
    raise HTTPException(status_code=400, detail="User not found")
  if expires_delta:
    expire = datetime.now(timezone.utc) + expires_delta
  else:
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
  to_encode.update({"exp": expire})
  encoded_jwt = jwt.encode(to_encode, SUPER_SECRET_KEY, algorithm="HS256")
  return encoded_jwt


async def get_login(credentials: Annotated[HTTPBasicCredentials, Depends(basic_security)], users: AsyncSession) -> Login:
  resolution = Login(status=ErrorCode.INVALID_CREDENTIALS)
  result = await users.execute(select(User_DB).filter(User_DB.username == credentials.username))
  user = result.scalars().first()

  if not user:
    # Simulate verifying a password
    pwd_context.dummy_verify()
    raise HTTPException(status_code=400, detail="Invalid username or password")
  if user.disabled:
    raise HTTPException(status_code=400, detail="User is disabled")
  if (verify_password(credentials.password, user.hashed_password)):
    resolution.user = User(username=user.username, email=user.email, full_name=user.full_name, disabled=user.disabled, hashed_password=user.hashed_password, secret_key=user.secret_key, otp_enabled=user.otp_enabled)
    if resolution.user.otp_enabled:
      resolution.status = ErrorCode.OTP_REQUIRED
    else:
      resolution.status = ErrorCode.SUCCESS
  return resolution

# Registers a new user if username is not already taken, does not configure OTP
async def register_user(credentials: Annotated[HTTPBasicCredentials, Depends(basic_security)], users: AsyncSession):
  if not credentials.username or not credentials.password:
    raise HTTPException(status_code=401, detail="Missing/Invalid credentials")
  result = await users.execute(select(User_DB).filter(User_DB.username == credentials.username))
  user = result.scalars().first()
  if user:
    raise HTTPException(status_code=400, detail="User already exists")
  
  secret_key = pyotp.random_base32()
  users.add(User_DB(username=credentials.username,
                 hashed_password=hash_password(credentials.password),
                 secret_key=secret_key,
                 otp_enabled=False,
                 disabled=False))
  await users.commit()
  return {"message": f"User {credentials.username} registered successfully."}

async def get_current_user(token: Annotated[str, Depends(bearer_security)], users: AsyncSession) -> User:
  credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
  try:
    payload = jwt.decode(token, key=SUPER_SECRET_KEY, algorithms=["HS256"])
    username: str = payload.get("sub")
    if not username:
      raise credential_exception
    
    result = await users.execute(select(User_DB).filter(User_DB.username == username))
    user = result.scalars().first()

    if not user:
      raise credential_exception
    if user.disabled:
      raise credential_exception
  except InvalidTokenError:
    raise credential_exception
  
  return User(username=user.username, email=user.email, full_name=user.full_name, disabled=user.disabled, hashed_password=user.hashed_password, secret_key=user.secret_key, otp_enabled=user.otp_enabled)


# OTP Stuff:

async def check_otp(otp: Optional[str], secret_key: str):
  previous_otp = TOTP(secret_key).at(datetime.now() - timedelta(seconds=30))
  return TOTP(secret_key).verify(otp) or (otp == previous_otp)

async def get_login_response(login: Annotated[Login, Depends(get_login)], users: AsyncSession, otp: Optional[str] = None) -> Login_Response:
  resolution = Login_Response(status=login.status)

  result = await users.execute(select(User_DB).filter(User_DB.username == login.user.username))
  user = result.scalars().first()

  if not user:
    raise HTTPException(status_code=400, detail="User does not exist")

  if user.otp_enabled:
    resolution.status = ErrorCode.OTP_REQUIRED
    if otp and await check_otp(otp, user.secret_key):
      resolution.status = ErrorCode.SUCCESS
      resolution.token = await create_jwt({"sub": user.username}, users=users)
    else:
      print(TOTP(user.secret_key).now())
      resolution.status = ErrorCode.INVALID_OTP
  else:
    resolution.status = ErrorCode.SUCCESS
    resolution.token = await create_jwt({"sub": user.username}, users=users)
  return resolution