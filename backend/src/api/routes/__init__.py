"""HTTP routes.

Do NOT import every module here. Several modules import each other and some
reach into models that reference back, so eager imports create cycles.

Import the specific module you need directly:

    from src.api.routes.auth_route import auth_bp

Every blueprint is registered by app.py unconditionally, so which endpoints
exist is decided by what app.py imports and mounts.
"""