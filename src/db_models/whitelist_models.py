from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Whitelist_Base(DeclarativeBase):
  pass

class Whitelist_DB(Whitelist_Base):
  __tablename__ = 'whitelist'
  ip:Mapped[str] = mapped_column(nullable=False)
  rowid:Mapped[int] = mapped_column(primary_key=True)