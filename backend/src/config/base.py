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

    ## Platform (super-admin) JWT.
    ##
    ## Deliberately a different secret from the tenant JWT above, so a token
    ## minted for a hotel can never be accepted on a platform route and a
    ## platform token can never be accepted on a hotel route -- even if one
    ## secret leaks, the other stays useless. See docs/multi-tenancy.md section 6.3.
    ##
    ## Unset by default on purpose: platform routes then refuse every call with a
    ## loud error instead of degrading into "any token is fine". Set it in .env
    ## (and in the deployment) to enable platform administration.
    PLATFORM_JWT_SECRET_KEY = os.getenv("PLATFORM_JWT_SECRET_KEY")
    PLATFORM_JWT_ALGORITHM = os.getenv("PLATFORM_JWT_ALGO", "HS256")
    PLATFORM_JWT_EXPIRES_MIN = int(os.getenv("PLATFORM_JWT_EXPIRES_MIN", 60))

    ## Platform console session lifetime.
    ##
    ## The platform admin has no refresh cookie of its own, so this expiry is the
    ## whole session lifetime. It defaults longer than the 30-minute hotel access
    ## token because an operator switching hotels would otherwise be logged out
    ## mid-work, but short enough that a stolen token goes stale. The platform
    ## token is also revocable through `super_admin_tokens`, so this is a
    ## backstop rather than the only defence.
    SUPER_ADMIN_TOKEN_EXPIRES_MIN = int(os.getenv("SUPER_ADMIN_TOKEN_EXPIRES_MIN", 60))

    ## Brute-force guard on the platform sign-in. After this many consecutive
    ## wrong passwords the account is locked for `SUPER_ADMIN_LOCKOUT_MINUTES`;
    ## a correct password clears the counter. The platform login is the most
    ## valuable one on the system -- it has no tenant scope -- so it is the one
    ## that most needs a ceiling on guesses.
    SUPER_ADMIN_MAX_LOGIN_ATTEMPTS = int(os.getenv("SUPER_ADMIN_MAX_LOGIN_ATTEMPTS", 5))
    SUPER_ADMIN_LOCKOUT_MINUTES = int(os.getenv("SUPER_ADMIN_LOCKOUT_MINUTES", 15))

    ## Bootstrap credentials for the FIRST platform admin, seeded by
    ## src/database/seeders/platform_admin_seeder.py. Overridable per
    ## environment; the defaults exist so a fresh database can be signed into at
    ## all, and MUST be changed before anything is exposed.
    PLATFORM_ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "platform@admin.local")
    PLATFORM_ADMIN_PASSWORD = os.getenv("PLATFORM_ADMIN_PASSWORD", "Platform@123")
    PLATFORM_ADMIN_FIRST_NAME = os.getenv("PLATFORM_ADMIN_FIRST_NAME", "Platform")
    PLATFORM_ADMIN_LAST_NAME = os.getenv("PLATFORM_ADMIN_LAST_NAME", "Admin")

    ## The public origin this deployment is reached at. Handed to the platform
    ## console by `GET /api/v1/platform/config` so one build serves every
    ## environment and the panel can never print a development host in
    ## production.
    ##
    ##   development  PUBLIC_BASE_URL=http://localhost:4200
    ##   production   PUBLIC_BASE_URL=https://console.example.com
    ##
    ## Read ONCE, at process start: editing `.env` does not change a running
    ## server. Restart the backend, then reload the console.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:4200")

    ## Multi-tenancy
    ##
    ## Base domain tenant subdomains hang off in production, e.g. "hms.example.com"
    ## so that acme.hms.example.com is tenant "acme". Left unset in development
    ## on purpose: the API is then on a different origin than the app, so the
    ## tenant arrives in the X-Tenant header rather than in Host.
    TENANT_BASE_DOMAIN = os.getenv("TENANT_BASE_DOMAIN")

    ## Header the frontend uses to name the tenant when the subdomain is not
    ## visible to the API. See src/api/middlewares/tenant_resolver.py.
    TENANT_HEADER_NAME = os.getenv("TENANT_HEADER_NAME", "X-Tenant")

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

    ## CORS
    ##
    ## Comma-separated list of browser origins allowed to call the API. Left
    ## unset in development, where app.py admits the dev server on
    ## `localhost:4200` and any hotel subdomain of it (`acme.localhost:4200`).
    ## Production sets this to its own origins.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS")

    ## Timezone the business trades in. Every "today" boundary in a report is
    ## computed in THIS zone, not the server's: under Asia/Kolkata the report for
    ## 9 Oct begins at 18:30 UTC on 8 Oct. Get this wrong and the opening and
    ## closing hours of every daily figure land in the wrong bucket.
    ## IANA name, e.g. Asia/Kolkata, Europe/London, America/New_York.
    BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")