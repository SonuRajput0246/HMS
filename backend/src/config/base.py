import os

from dotenv import load_dotenv


load_dotenv()


class BaseConfig:

    ## Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    ## SQLAlchemy connection pool settings (VERY IMPORTANT)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 20))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 30))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 1800))  # 30 min

    ## JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGO", "HS256")
    JWT_ACCESS_TOKEN_EXPIRES_MIN = int(os.getenv("JWT_ACCESS_EXPIRES_MIN", 15))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRES_DAYS", 7))

    ## SMTP
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

    ## OTP
    OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", 10))
    OTP_ATTEMPTS = int(os.getenv("OTP_ATTEMPTS", 3))

    ## Cookies
    COOKIE_SECURE = os.getenv("COOKIE_SECURE")
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE")

    ## Timezone the business trades in. Every "today" boundary in a report is
    ## computed in THIS zone, not the server's: under Asia/Kolkata the report for
    ## 9 Oct begins at 18:30 UTC on 8 Oct. Get this wrong and the opening and
    ## closing hours of every daily figure land in the wrong bucket.
    ## IANA name, e.g. Asia/Kolkata, Europe/London, America/New_York.
    BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")