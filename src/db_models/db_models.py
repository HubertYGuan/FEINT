from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class DB_Base(DeclarativeBase):
  pass

class Event(DB_Base):
  __tablename__ = 'events'
  timestamp:Mapped[str] = mapped_column(nullable=False)
  raw_timestamp:Mapped[float] = mapped_column(nullable=False)
  description:Mapped[str]
  rowid:Mapped[int] = mapped_column(primary_key=True)

class Todo(DB_Base):
  __tablename__ = 'todo'
  description:Mapped[str] = mapped_column(nullable=False)
  bRepeats:Mapped[bool] = mapped_column(nullable=False)
  rowid:Mapped[int] = mapped_column(primary_key=True)