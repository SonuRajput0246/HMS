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

## Routes, grouped by bucket. Which group an endpoint belongs to is decided by
## the `if app.config[...]` gates in create_app(), not by the import list.
##
## Imports are unconditional on purpose. A CMS process still has to be able to
## import this module, and the gate below decides what actually gets registered.
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

### CMS (Cafe Management System) routes
from src.api.routes.cms.table_zone_route import table_zone_bp
from src.api.routes.cms.table_route import table_bp
from src.api.routes.cms.customer_route import customer_bp
from src.api.routes.cms.order_route import order_bp
from src.api.routes.cms.recipe_category_route import recipe_category_bp
from src.api.routes.cms.recipe_route import recipe_bp
from src.api.routes.cms.recipe_ingredient_route import recipe_ingredient_bp
from src.api.routes.cms.kds_route import kds_bp
from src.api.routes.cms.pos_route import pos_bp
from src.api.routes.cms.report_route import report_bp

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
import src.api.events.cms_events

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
    ## Only the active instance's blueprints are registered. An unregistered
    ## blueprint means its routes 404 rather than existing-but-hidden, which is
    ## what we want: a CMS deployment should not accept a room-booking payload
    ## just because the endpoint is undocumented. The frontend hides those
    ## screens; this stops the calls reaching the database at all.
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(user_bp, url_prefix="/api/v1/user")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(common_bp, url_prefix="/api/v1/common")
    app.register_blueprint(account_bp, url_prefix="/api/v1/user-account")
    app.register_blueprint(template_bp, url_prefix="/api/v1/template")

    ## Inventory is shared, not HMS-only. The models, the seeders and the
    ## category/unit reference data all live in common/, and on the CMS side
    ## Recipe.calculate_cost_from_ingredients() multiplies each ingredient
    ## quantity by Inventory.unit_cost. Gating this blueprint on IS_HMS left
    ## CMS holding seeded stock it could neither read nor price against: the
    ## recipe ingredient grid fetches its options from /inventory/get and got
    ## a 404, so there was no way to maintain the costs the menu is built on.
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")

    if app.config["IS_HMS"]:
        app.register_blueprint(reservation_bp, url_prefix="/api/v1/reservation")
        app.register_blueprint(room_bp, url_prefix="/api/v1/room")
        app.register_blueprint(guest_bp, url_prefix="/api/v1/guest")

    if app.config["IS_CMS"]:
        app.register_blueprint(table_zone_bp, url_prefix="/api/v1/table-zone")
        app.register_blueprint(table_bp, url_prefix="/api/v1/table")
        app.register_blueprint(customer_bp, url_prefix="/api/v1/customer")
        app.register_blueprint(order_bp, url_prefix="/api/v1/order")
        app.register_blueprint(recipe_category_bp, url_prefix="/api/v1/recipe-category")
        app.register_blueprint(recipe_bp, url_prefix="/api/v1/recipe")
        app.register_blueprint(recipe_ingredient_bp, url_prefix="/api/v1/recipe-ingredient")
        app.register_blueprint(kds_bp, url_prefix="/api/v1/kds")
        app.register_blueprint(pos_bp, url_prefix="/api/v1/pos")
        app.register_blueprint(report_bp, url_prefix="/api/v1/report")

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