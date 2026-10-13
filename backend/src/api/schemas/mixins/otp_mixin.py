from src.api.schemas.fields.otp import otp_field


class OTPFieldMixin:
    otp = otp_field('OTP')