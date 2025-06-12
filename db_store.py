
from config_reader import config
from datetime import datetime, timedelta
from sqlalchemy import  Integer, Text, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.orm import mapped_column, relationship
from typing import List, Optional



# Адрес БД
sqlite_database = config.database_address.get_secret_value()
# Cоздаем движок SqlAlchemy
engine = create_engine(sqlite_database, echo=False)


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = 'users'

    tg_id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[int]] = mapped_column(Text)
    store: Mapped[Optional[int]] = mapped_column(Text)

    reports: Mapped[List['Reports']] = relationship('Reports', back_populates='users')


class Reports(Base):
    __tablename__ = 'reports'

    reports_id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    sales: Mapped[Optional[str]] = mapped_column(Integer)
    remainings: Mapped[Optional[str]] = mapped_column(Integer)
    user: Mapped[Optional[int]] = mapped_column(ForeignKey('users.tg_id'))

    users: Mapped[Optional['Users']] = relationship('Users', back_populates='reports')


# Добавляем пользователя в БД если отуствует
def add_user(tg_id, name="", store=""):

    # Создаем объект пользователя
    user = Users(tg_id=tg_id, name=name, store=store)

    # Проверяем наличие записи пользователя в БД
    query = db.query(Users).filter(Users.tg_id==tg_id).first()
    
    if query is None:        
        # Добавляем пользователя в БД
        db.add(user)
        db.commit()
        db.refresh(user) 
        print(f"Пользователь [{user.tg_id}] - {user.name} ({user.store}) добавлен в БД!") 

    else: 
        print(f"Пользователь [{user.tg_id}] - {user.name} ({user.store}) уже существует в БД!") 
    
    return user


# Cоздаем таблицы
Base.metadata.create_all(bind=engine)
