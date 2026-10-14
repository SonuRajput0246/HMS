from flask import Flask
from flask_cors import CORS
from src.config import get_config
from src.api.extensions import bcrypt
from src.database.session import db_session
from src.database.tenant_context import clear_tenant_context
from src.api.utils.error_handlers import register_error_handlers
from src.api.middlewares.tenant_resolver import init_tenant_resolver

## Routes. Every blueprint below is registered unconditionally -- there is no
## instance switch, so an endpoint either exists here or was never written.
##
## Imports are unconditional on purpose, and the order is only for readability:
## identity/access, then reference data, then the hotel domain.
from src.api.routes.auth_route import auth_bp
from src.api.routes.user_route import user_bp
from src.api.routes.admin_route import admin_bp
from src.api.routes.common_route import common_bp
from src.api.routes.user_account_route import account_bp
from src.api.routes.template_route import template_bp
from src.api.routes.inventory_route import inventory_bp
from src.api.routes.room_route import room_bp
from src.api.routes.guest_route import guest_bp
from src.api.routes.reservation_route import reservation_bp
from src.api.routes.platform_route import platform_bp

## Event listeners. Imported purely for side effect: each module registers
## SQLAlchemy before_insert / before_update hooks as it is imported. That is not
## optional decoration -- BaseModel.created_at / updated_at are nullable=False
## with no column default, so a row inserted without a listener raises
## MySQLdb.IntegrityError 1048 on MySQL.
import src.api.events.user_events
import src.api.events.email_otp_events
import src.api.events.role_events
import src.api.events.inventory_events
import src.api.events.room_events
import src.api.events.reservation_events
import src.api.events.guest_events
import src.api.events.payment_events
import src.api.events.tenant_events
import src.api.events.platform_user_events

def create_app():
    app = Flask(__name__)

    ## Load configuration
    app.config.from_object(get_config())

    ## Enable CORS
    CORS(
        app,
        resources={r"/*": {"origins": "http://localhost:4200"}},
        supports_credentials=True
    )

    ## Initialize extensions
    bcrypt.init_app(app)

    ## Resolve the tenant onto flask.g before any route runs. Registered before
    ## the blueprints so that every one of them, present and future, is covered
    ## by the same hook rather than each having to opt in.
    init_tenant_resolver(app)

    ## Register blueprints
    ##
    ## The module tree seeded into `modules` and the endpoints that exist are
    ## the same list, so an endpoint that is unreachable here is one that was
    ## never written.
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(user_bp, url_prefix="/api/v1/user")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(common_bp, url_prefix="/api/v1/common")
    app.register_blueprint(account_bp, url_prefix="/api/v1/user-account")
    app.register_blueprint(template_bp, url_prefix="/api/v1/template")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(room_bp, url_prefix="/api/v1/room")
    app.register_blueprint(guest_bp, url_prefix="/api/v1/guest")
    app.register_blueprint(reservation_bp, url_prefix="/api/v1/reservation")

    ## Platform administration, above every hotel. Exempt from tenant resolution
    ## (see TENANT_EXEMPT_PREFIXES) and gated by its own secret; see
    ## src/api/middlewares/platform_auth.py.
    app.register_blueprint(platform_bp, url_prefix="/api/v1/platform")

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """
        Ensures that the database session is removed at the end of every request.
        This releases the connection back to the SQLAlchemy pool.
        """
        ## Drop the tenant scope as well. Both the session and the worker thread
        ## are pooled, so a tenant left set here would silently scope whichever
        ## request landed on this thread next.
        clear_tenant_context()
        db_session.remove()

    ## Error Handler
    register_error_handlers(app)


    return app