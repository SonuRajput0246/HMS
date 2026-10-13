from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from src.config import get_config

## Load the configuration based on the environment
config = get_config()


## 1. Initialize the Engine
## This creates the connection pool based on your BaseConfig settings
engine = create_engine(
    config.DATABASE_URL,
    pool_size=config.DB_POOL_SIZE,
    max_overflow=config.DB_MAX_OVERFLOW,
    pool_timeout=config.DB_POOL_TIMEOUT,
    pool_recycle=config.DB_POOL_RECYCLE,
    pool_pre_ping=True  # Automatically reconnects if the DB server drops the connection
)

## 2. Create a Session Factory
## autocommit=False ensures we control transactions manually (standard practice)
session_factory = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

## 3. Create a Scoped Session
## This is thread-safe and perfect for Flask production environments
db_session = scoped_session(session_factory)