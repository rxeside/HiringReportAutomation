import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///cache/huntflow.db"

os.makedirs("cache", exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Applicant(Base):
    __tablename__ = "applicants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    applicant_id = Column(Integer, index=True)

    vacancy = Column(String)
    vacancy_state = Column(String)
    recruiter_id = Column(Integer)
    source = Column(String)
    created_at = Column(DateTime)

    current_status = Column(String)
    hf_status = Column(String, nullable=True)

    rejection_reason = Column(String, nullable=True)
    offer_date = Column(DateTime, nullable=True)
    hired_date = Column(DateTime, nullable=True)
    is_hired = Column(Boolean, default=False)
    log_dates = Column(String, nullable=True)


class Coworker(Base):
    __tablename__ = "coworkers"
    id = Column(Integer, primary_key=True)
    name = Column(String)


class SystemState(Base):
    __tablename__ = "system_state"
    key = Column(String, primary_key=True)
    value = Column(String)


Base.metadata.create_all(bind=engine)