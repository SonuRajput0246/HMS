import pyotp

def generate_secret():
    return pyotp.random_base32()

def get_uri(email, secret):
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name="HMS-2026"
    )

def verify_otp(secret, otp):
    return pyotp.TOTP(secret).verify(otp)