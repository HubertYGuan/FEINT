from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class User_Base(DeclarativeBase):
    pass


class User_DB(User_Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(nullable=True)
    full_name: Mapped[str] = mapped_column(nullable=True)
    disabled: Mapped[bool] = mapped_column(nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    secret_key: Mapped[str] = mapped_column(nullable=False)
    otp_enabled: Mapped[bool] = mapped_column(nullable=False)
    rowid: Mapped[int] = mapped_column(primary_key=True)
