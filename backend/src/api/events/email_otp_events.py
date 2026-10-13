from sqlalchemy import event
from flask import current_app
from src.api.models import EmailOTP
from datetime import datetime, timezone, timedelta



### BEFORE INSERT
@event.listens_for(EmailOTP, "before_insert")
def email_otp_before_insert(mapper, connection, target):
    now = datetime.now(timezone.utc)
    otp_expiry_minutes = current_app.config["OTP_EXPIRY_MINUTES"]
    expires_at = (now + timedelta(minutes=otp_expiry_minutes))

    ## Auto-set timestamps
    target.created_at = now
    target.updated_at = now
    target.expires_at = expires_at


### BEFORE UPDATE
@event.listens_for(EmailOTP, "before_update")
def email_otp_before_update(mapper, connection, target):
    now = datetime.now(timezone.utc)

    ## Auto-update the modified timestamp
    target.updated_at = now