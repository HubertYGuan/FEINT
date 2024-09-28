from sqlalchemy import Column, MetaData, select, String, Table, create_engine, insert
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db_models.db_models import DB_Base, Event, Todo
from db_models.user_models import User_Base, User_DB
from db_models.whitelist_models import Whitelist_Base, Whitelist_DB

import asyncio

# Need to eventually make these db files unique to each user

# For some reason trying to connect to :///db/database.sqlite3 will raise errors only if run from src/
DB_engine = create_async_engine('sqlite+aiosqlite:////var/lib/db_data/database.sqlite3', connect_args={'check_same_thread': False})

DB_Session = async_sessionmaker(DB_engine)

async def Get_DB():
  async with DB_engine.begin() as conn:
    await conn.run_sync(DB_Base.metadata.create_all)
    db = DB_Session()
  try:
    yield db
  finally:
    await db.close()


User_engine = create_async_engine('sqlite+aiosqlite:////var/lib/db_data/users.sqlite3', connect_args={'check_same_thread': False})

User_Session = async_sessionmaker(User_engine)

async def Get_Users():
  async with User_engine.begin() as conn:
    await conn.run_sync(User_Base.metadata.create_all)
    users = User_Session()
  try:
    yield users
  finally:
    await users.close()

Whitelist_engine = create_engine('sqlite:////var/lib/db_data/whitelist.sqlite3', connect_args={'check_same_thread': False})
Whitelist_Session = Session(bind=Whitelist_engine)
def Get_Whitelist():
  return Whitelist_Session
      
async def Drop_Tables():
  async with DB_engine.begin() as conn:
    await conn.run_sync(DB_Base.metadata.drop_all)
  async with User_engine.begin() as conn:
    await conn.run_sync(User_Base.metadata.drop_all)
  Whitelist_Base.metadata.drop_all(bind=Whitelist_engine)

async def Create_Tables():
  async with DB_engine.begin() as conn:
    await conn.run_sync(DB_Base.metadata.create_all)
  async with User_engine.begin() as conn:
    await conn.run_sync(User_Base.metadata.create_all)
  Whitelist_Base.metadata.create_all(bind=Whitelist_engine)

def main():
  # Remove below if you want data to persist
  asyncio.run(Drop_Tables())
  asyncio.run(Create_Tables())

if __name__ == '__main__':
  main()