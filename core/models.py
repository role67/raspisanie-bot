import datetime
from sqlalchemy import (BigInteger, Column, String, Integer, DateTime, Date,
                        ForeignKey, func)
from core.database import Base

class User(Base):
    """Модель пользователя."""
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, index=True)
    group_name = Column(String, ForeignKey('groups.name', ondelete='SET NULL'), nullable=True)
    join_date = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now(), onupdate=func.now())

class Group(Base):
    """Модель учебной группы."""
    __tablename__ = 'groups'
    name = Column(String, primary_key=True, index=True)
    student_count = Column(Integer, default=0)

class Schedule(Base):
    """Модель основного расписания."""
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    group_name = Column(String, ForeignKey('groups.name', ondelete='CASCADE'), index=True)
    day_of_week = Column(Integer) # 0-понедельник, 6-воскресенье
    week_type = Column(String) # "четная" или "нечетная"
    pair_number = Column(Integer)
    subject = Column(String, nullable=True)
    teacher = Column(String, nullable=True)
    room = Column(String, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Replacement(Base):
    """Модель замен в расписании."""
    __tablename__ = 'replacements'
    id = Column(Integer, primary_key=True)
    group_name = Column(String, ForeignKey('groups.name', ondelete='CASCADE'), index=True)
    date = Column(Date, index=True)
    pair_number = Column(Integer)
    original_subject = Column(String, nullable=True)
    new_subject = Column(String, nullable=True)
    teacher = Column(String, nullable=True)
    room = Column(String, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Log(Base):
    """Модель для логирования действий пользователя."""
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    action = Column(String)
    timestamp = Column(DateTime, default=func.now(), index=True)

class FileHash(Base):
    """Модель для хранения хешей файлов."""
    __tablename__ = 'file_hashes'
    file_url = Column(String, primary_key=True)
    file_hash = Column(String)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
