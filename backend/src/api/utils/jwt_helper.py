from flask import request, g
import jwt
from flask import current_app


def get_user_id_from_jwt():
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise Exception("Authorization token missing")

    token = auth_header.split(" ")[1]

    payload = jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]]
    )

    user_id = payload.get("user_id")
    if not user_id:
        raise Exception("Invalid token")

    return user_id


def get_current_user_id(default=None):
    """Read the authenticated user id from Flask's request-scoped globals.

    Prefer this over `get_user_id_from_jwt` inside service code. The
    `jwt_required` decorator has already decoded the token, verified the user
    exists and is active, and stored the row in `g.current_user`, so calling it
    again means decoding the JWT a second time for no benefit.

    Returns `default` when there is no request context or the endpoint was not
    protected, which keeps services callable from seeders and CLI scripts.
    """
    user = g.get("current_user") if g else None

    if user is None:
        return default

    return getattr(user, "id", default)
