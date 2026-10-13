import logging
from flask import Flask
from flask import jsonify
from flask_cors import CORS
from src.config import get_config
from src.api.extensions import bcrypt
from src.api.utils.errors import APIError
from src.database.session import db_session
from marshmallow.exceptions import MarshmallowError
from sqlalchemy.sql.operators import json_getitem_op
from src.api.utils.error_handlers import register_error_handlers

## Routes, grouped by bucket. `common/` is shared infrastructure, `hms/` is the
## hotel domain. Everything registered below always exists -- there is no
## instance switch, so an endpoint is either part of HMS or it is not written.
from src.api.routes.common.auth_route import auth_bp
from src.api.routes.common.user_route import user_bp
from src.api.routes.common.admin_route import admin_bp
from src.api.routes.common.common_route import common_bp
from src.api.routes.common.user_account_route import account_bp
from src.api.routes.common.template_route import template_bp

## HMS (hotel) routes
from src.api.routes.hms.room_route import room_bp
from src.api.routes.hms.guest_route import guest_bp
from src.api.routes.common.inventory_route import inventory_bp
from src.api.routes.hms.reservation_route import reservation_bp

import src.api.events.user_events
import src.api.events.email_otp_events
import src.api.events.role_events
import src.api.events.inventory_events
import src.api.events.room_events
import src.api.events.reservation_events
import src.api.events.guest_events
import src.api.events.folio_events
import src.api.events.folio_charges_events
import src.api.events.invoice_events
import src.api.events.invoice_item_events
import src.api.events.payment_events
import src.api.events.refund_events

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

    ## Register blueprints
    ##
    ## Every blueprint is registered unconditionally. There is no instance
    ## switch: the module tree seeded into `modules` and the endpoints that
    ## exist are the same list, so an endpoint that is unreachable here is one
    ## that was never written.
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(user_bp, url_prefix="/api/v1/user")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(common_bp, url_prefix="/api/v1/common")
    app.register_blueprint(account_bp, url_prefix="/api/v1/user-account")
    app.register_blueprint(template_bp, url_prefix="/api/v1/template")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")

    ## HMS (hotel) routes
    app.register_blueprint(reservation_bp, url_prefix="/api/v1/reservation")
    app.register_blueprint(room_bp, url_prefix="/api/v1/room")
    app.register_blueprint(guest_bp, url_prefix="/api/v1/guest")

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