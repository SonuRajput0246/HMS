import re
from flask import Flask
from flask_cors import CORS
from src.config import get_config
from src.api.extensions import bcrypt
from src.database.session import db_session
# from src.database.tenant_context import clear_tenant_context
from src.api.utils.error_handlers import register_error_handlers
# from src.api.middlewares.tenant_resolver import init_tenant_resolver

## Shared infrastructure routes, then the hotel domain routes. Every blueprint
## below is registered unconditionally -- this app is HMS only, so there is no
## instance gate and no route tree that differs between deployments.
from src.api.routes.auth_route import auth_bp
from src.api.routes.user_route import user_bp
from src.api.routes.admin_route import admin_bp
from src.api.routes.common_route import common_bp
from src.api.routes.user_account_route import account_bp
from src.api.routes.template_route import template_bp
from src.api.routes.inventory_route import inventory_bp

## The platform console: manages tenants, so it owns no tenant and sits in its
## own URL space. Registered before the cafe routes only for readability -- the
## rule sets do not overlap.
from src.api.routes.super_admin_route import super_admin_bp

### HMS (Hotel Management System) routes
from src.api.routes.room_route import room_bp
from src.api.routes.guest_route import guest_bp
from src.api.routes.reservation_route import reservation_bp

## Timestamps and soft-delete stamps are registered once, globally, in
## src/api/events/base_events.py, which the model registry (src.api.models)
## imports for its side effect at its bottom. Nothing needs importing here: the
## route imports above pull in services, which import the registry. Registering
## listeners only from app.py is what made created_at a NOT NULL violation
## waiting for the first non-Flask caller -- a seeder, alembic, a script.


def create_app():
    app = Flask(__name__)

    ## Load configuration
    app.config.from_object(get_config())

    ## Enable CORS
    CORS(
        app,
        resources={r"/*": {"origins": [
            "http://localhost:4200",
            r"http://[a-z0-9-]+\.localhost:4200$",
        ]}},
        supports_credentials=True
    )

    ## Initialize extensions
    bcrypt.init_app(app)

    ## Register blueprints
    ##
    ## Every blueprint is registered unconditionally. This used to be gated on
    ## an INSTANCE_TYPE switch so one codebase could serve either product; the
    ## hotel half is gone, so the gate had nothing left to decide.
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(user_bp, url_prefix="/api/v1/user")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(common_bp, url_prefix="/api/v1/common")
    app.register_blueprint(account_bp, url_prefix="/api/v1/user-account")
    app.register_blueprint(template_bp, url_prefix="/api/v1/template")

    ## Platform admin. Its own prefix because its guard, its identity table and
    ## its lack of a tenant context are all different from the routes below.
    app.register_blueprint(super_admin_bp, url_prefix="/api/super-admin")

    ## Inventory is shared with the CMS domain, not a leftover of the hotel
    ## one. Recipe.calculate_cost_from_ingredients() multiplies each ingredient
    ## quantity by Inventory.unit_cost, and the recipe ingredient grid fetches
    ## its options from /inventory/get -- so the menu cannot be priced without
    ## these endpoints.
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")

    app.register_blueprint(room_bp, url_prefix="/api/v1/room")
    app.register_blueprint(guest_bp, url_prefix="/api/v1/guest")
    app.register_blueprint(reservation_bp, url_prefix="/api/v1/reservation")

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """
        Ensures that the database session is removed at the end of every request.
        This releases the connection back to the SQLAlchemy pool.
        """
        db_session.remove()

    ## Error Handler
    register_error_handlers(app)


    return app