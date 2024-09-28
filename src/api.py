# Maybe should create individual databases for each user

from fastapi import FastAPI, HTTPException, Depends, Response, Request, status
from fastapi.responses import StreamingResponse
from typing import Annotated, Optional
from fastapi.security import HTTPBearer, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from databaseinit import Get_DB, Get_Users, Get_Whitelist
from db_models.user_models import User_DB
from db_models.db_models import Event, Todo
from db_models.whitelist_models import Whitelist_DB
from sqlalchemy import select, update, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
import time
import datetime
import NotifyCalendar as NotifyCalendar
import auth
import pyotp
import qrcode
import io
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="../.env")
BACKEND_URL = os.getenv('BACKEND_URL')
FRONTEND_URL = os.getenv('FRONTEND_URL')
FRONTEND_HOST = os.getenv('FRONTEND_HOST')

# Singleton class for storing temporary data, I don't think it is unique to every user so it should actually instead be able to have many instancs
class temp_storage(BaseModel):
  temp_login_response: Optional[auth.Login_Response] = None
  temp_login: Optional[auth.Login] = None
  ip_whitelist: list[str] = ['']
  def __new__(cls):
    if not hasattr(cls, 'instance'):
      cls.instance = super().__new__(cls)
    return cls.instance

temp = temp_storage()



app = FastAPI()

bearer_security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, BACKEND_URL],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Does not work in the container. TODO: Change to API key authentication
'''
@app.middleware("http")
async def validate_ip(request: Request, call_next):
  whitelist = Get_Whitelist()
  results = whitelist.execute(select(Whitelist_DB))
  list_of_entries = results.scalars().all()
  temp.ip_whitelist = [entry.ip for entry in list_of_entries]
  temp.ip_whitelist.append(FRONTEND_HOST)
  if request.client.host not in temp.ip_whitelist:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
  response = await call_next(request)
  return response
'''

@app.get("/todo/")
async def todo_root(todos: AsyncSession = Depends(Get_DB)):
  results = await todos.execute(select(Todo))
  todo_list = results.scalars().all()
  return {"Here's a list of things you need to do:": todo_list}

@app.post("/todo/add/")
async def add_todo(description: str, bRepeats: bool, todos: AsyncSession = Depends(Get_DB)):
  await todos.execute(insert(Todo).values(description=description, bRepeats=bRepeats))
  await todos.commit()
  return

@app.put("/todo/update/{rowid}")
async def update_todo(rowid: int | None = None, description: str | None = None, bRepeats: bool | None = None, todos: AsyncSession = Depends(Get_DB)):
  await todos.execute(update(Todo).where(Todo.rowid == rowid).values(description=description, bRepeats=bRepeats))
  await todos.commit()
  return

@app.delete("/todo/delete/")
async def delete_todo_by_description(description: str, todos: AsyncSession = Depends(Get_DB)):
  await todos.execute(delete(Todo).where(Todo.description == description))
  await todos.commit()
  return {"message": f"Todo with description '{description}' deleted successfully"}

@app.delete("/todo/delete/{rowid}")
async def delete_todo_by_id(rowid: int, todos: AsyncSession = Depends(Get_DB)):
  await todos.execute(delete(Todo).where(Todo.rowid == rowid))
  await todos.commit()
  return {"message": f"Todo with id {rowid} deleted successfully"}

@app.post("/notify/")
async def notify(message: str | None = None, db: AsyncSession = Depends(Get_DB)):
  # Store the list of todo messages in a list of strings
  results = await db.execute(select(Todo))
  todo_list = results.scalars().all()
  todo_list = [entry.description for entry in todo_list]

  # Add an API call to Google Calendar
  NotifyCalendar.notify(todo_list)

  # Add an entry to the events table
  await db.execute(insert(Event).values(timestamp=datetime.datetime.now(), raw_timestamp=time.time(), description=f"Notification: {message}"))

  # Remove the non-repeating entries in todo
  await db.execute(delete(Todo).where(Todo.bRepeats == 0))

  await db.commit()

  # Select and print the latest entry
  results = await db.execute(select(Event).order_by(Event.rowid.desc()).limit(1))
  entry = results.scalars().first()

  return {"Latest entry: " : entry}
  

@app.get("/events/")
async def events_root(events: AsyncSession = Depends(Get_DB)):
  results = await events.execute(select(Event))
  return {"Here's a list of notify events:": results.scalars().all()}

@app.delete("/events/delete/{rowid}")
async def delete_event_by_id(rowid: int, events: AsyncSession = Depends(Get_DB)):
  await events.execute(delete(Event).where(Event.rowid == rowid))
  await events.commit()
  return {"message": f"Event with id {rowid} deleted successfully"}

# Authentication below:

@app.post("/auth/register/")
async def register(username: str, password: str, users: AsyncSession = Depends(Get_Users)):
  credentials: Annotated[HTTPBasicCredentials, Depends(auth.basic_security)] = HTTPBasicCredentials(username=username, password=password)
  try:
    await auth.register_user(credentials=credentials, users=users)
    return True
  except HTTPException:
    return False

@app.put("/auth/otp/enable/")
async def enable_otp(request: Request, users: AsyncSession = Depends(Get_Users)):
  try:
    token = request.cookies.get('token')
    if not token:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                          detail="Invalid token",
                          headers={"WWW-Authenticate": "Bearer"})
    user: auth.user = await auth.get_current_user(token, users=users)
    await users.execute(update(User_DB).where(User_DB.username == user.username).values(otp_enabled=True))
    await users.commit()
    return {"message": f"OTP enabled for user {user.username}"}
  except HTTPException:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password",
                        headers={"WWW-Authenticate": "Bearer"})
  
@app.put("/auth/otp/disable/")
async def disable_otp(request: Request, users: AsyncSession = Depends(Get_Users)):
  try:
    token = request.cookies.get('token')
    if not token:
      print('No token')
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                          detail="Invalid token",
                          headers={"WWW-Authenticate": "Bearer"})
    user: auth.user = await auth.get_current_user(token, users=users)
    await users.execute(update(User_DB).where(User_DB.username == user.username).values(otp_enabled=False))
    await users.commit()
    return {"message": f"OTP disabled for user {user.username}"}
  except HTTPException:
    print(HTTPException + 'Get current user failed')
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password",
                        headers={"WWW-Authenticate": "Bearer"})

@app.get("/auth/otp/generate/")
async def generate_qr_code(request: Request, users: AsyncSession = Depends(Get_Users)):
  try:
    user: auth.user = await auth.get_current_user(request.cookies.get('token'), users=users)
    totp = pyotp.TOTP(user.secret_key)
    qr_code = qrcode.make(totp.provisioning_uri(user.username, issuer_name="An Embedded System Web App"))
    img_byte_array = io.BytesIO()
    qr_code.save(img_byte_array)
    img_byte_array.seek(0)  # Reset the buffer position to the beginning
    return StreamingResponse(content=img_byte_array, media_type="image/png")
  except HTTPException:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password",
                        headers={"WWW-Authenticate": "Bearer"})

@app.get("/auth/token/read/")
def read_token(request: Request):
    token_value = request.cookies.get('token')
    return token_value

@app.get("/auth/token/verify/")
async def verify_user(request: Request, users: AsyncSession = Depends(Get_Users)):
  if not request.cookies.get('token'):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
  user = await auth.get_current_user(request.cookies.get('token'), users=users)
  if user:
    return user
  else:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)



@app.get("/auth/login/")
async def login_normal(username: str, password: str, users: AsyncSession = Depends(Get_Users)):
  credentials: Annotated[HTTPBasicCredentials, Depends(auth.basic_security)] = HTTPBasicCredentials(username=username, password=password)
  attempted_login = await auth.get_login(credentials=credentials, users=users)
  if attempted_login.status == auth.ErrorCode.INVALID_CREDENTIALS:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password",
                        headers={"WWW-Authenticate": "Bearer"})
  login_response = await auth.get_login_response(attempted_login, users=users)
  temp.temp_login = attempted_login
  temp.temp_login_response = login_response
  return login_response

@app.get("/auth/login/otp/")
async def login_otp(users: AsyncSession = Depends(Get_Users), otp: Optional[str] = None, enabling_otp: bool = False):
  if enabling_otp and (temp.temp_login_response.status == auth.ErrorCode.SUCCESS or temp.temp_login_response.status == auth.ErrorCode.INVALID_OTP):
    temp.temp_login_response.status = auth.ErrorCode.OTP_REQUIRED
  login_response = temp.temp_login_response
  login = temp.temp_login
  if not login_response:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials",
                        headers={"WWW-Authenticate": "Bearer"})
  if (login_response.status != auth.ErrorCode.OTP_REQUIRED) and (login_response.status != auth.ErrorCode.INVALID_OTP):
    print(login_response.status)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="OTP not enabled or invalid credentials",
                        headers={"WWW-Authenticate": "Bearer"})
  response = await auth.get_login_response(login, otp=otp, users=users)
  if response.status == auth.ErrorCode.INVALID_OTP:
    print(login_response.status)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid OTP",
                        headers={"WWW-Authenticate": "Bearer"})
  temp.temp_login_response = response
  return response

@app.get("/auth/login/token/")
async def login_for_token(response: Response):
  login_response = temp.temp_login_response
  if login_response.status != auth.ErrorCode.SUCCESS:
    print(login_response.status)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid username or password",
                        headers={"WWW-Authenticate": "Bearer"})
  response.set_cookie(key="token", value=login_response.token, httponly=True, samesite="lax", secure=True)
  return {"message": "Token set"}

@app.get("/whoami/")
async def whoami(request: Request, users: AsyncSession = Depends(Get_Users)):
  try:
    user = await auth.get_current_user(request.cookies.get('token'), users=users)
    return {"username": user.username}
  except HTTPException:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@app.get("/whitelist/")
async def whitelist_root(whitelist: AsyncSession = Depends(Get_Whitelist)):
  results = temp.ip_whitelist
  return {"Here's a list of whitelisted IPs:": results}