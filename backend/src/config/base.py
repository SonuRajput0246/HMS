import os
from enum import Enum

from dotenv import load_dotenv


load_dotenv()


class InstanceType(str, Enum):
    """The products a deployment can be configured as.

    Subclasses `str` so a value is directly usable as a Flask config value and
    compares equal to the plain string it was parsed from.
    """

    HMS = "HMS"
    CMS = "CMS"

    @classmethod
    def values(cls):
        return {m.value for m in cls}


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

    ## Instance Type
    ##
    ## Which product this process serves: HMS (hotel) or CMS (cafe). It
    ## decides which blueprints get registered, so a typo here must not fail
    ## quietly -- it raises at import, while the process is still starting and
    ## the stack trace points straight at this file.
    ##
    ## Keep in sync with `instance_type` in the frontend's
    ## src/assets/config.json. They are two halves of one switch: this one
    ## decides which endpoints exist, the other which screens load.
    _RAW_INSTANCE_TYPE = (os.getenv("INSTANCE_TYPE") or "").strip().upper()

    if _RAW_INSTANCE_TYPE not in InstanceType.values():
        raise RuntimeError(
            f"INSTANCE_TYPE must be one of {sorted(InstanceType.values())}, "
            f"got {os.getenv('INSTANCE_TYPE')!r}"
        )

    INSTANCE_TYPE = InstanceType(_RAW_INSTANCE_TYPE)
    IS_HMS = INSTANCE_TYPE is InstanceType.HMS
    IS_CMS = INSTANCE_TYPE is InstanceType.CMS

    ## Timezone the business trades in. Every "today" boundary in a report is
    ## computed in THIS zone, not the server's: under Asia/Kolkata the report for
    ## 9 Oct begins at 18:30 UTC on 8 Oct. Get this wrong and the opening and
    ## closing hours of every daily figure land in the wrong bucket.
    ## IANA name, e.g. Asia/Kolkata, Europe/London, America/New_York.
    BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")