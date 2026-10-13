from flask import jsonify
from marshmallow import ValidationError as MarshmallowError
from werkzeug.exceptions import HTTPException
from src.api.utils.errors import APIError
import logging

def register_error_handlers(app):
    @app.errorhandler(MarshmallowError)
    def handle_marshmallow_validation(err):
        """Catches Marshmallow validation errors globally"""
        ## err.message is a dict of fields and their error lists
        ## We take the first error message found
        first_error_field = next(iter(err.messages))
        first_error_message = err.messages[first_error_field][0]
        return jsonify({
            "status": False,
            "message": first_error_message
        }), 400

    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Catches all our custom errors"""
        response = {
            "status": False,
            "message": error.message
        }
        if error.payload:
            response["data"] = error.payload
        return jsonify(response), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Keep Werkzeug's own status codes intact.

        This has to exist because the generic Exception handler below catches
        everything, and HTTPException is itself an Exception. Without it every
        404 came back as a 500 "internal server error" with a full traceback
        logged as an unhandled fault -- including the 404s that blueprint
        gating returns on purpose when a CMS process is asked for a hotel
        endpoint. A client could not tell "this instance does not serve that"
        from "the server crashed", and real faults were buried under routine
        404 noise.

        Flask picks the most specific handler, so this wins over Exception for
        every HTTP status regardless of registration order.
        """
        ## The traceback is logged only for genuine server-side statuses.
        ## Reaching an unknown URL is a client mistake, not a fault, and
        ## logging it as one is what made the noise.
        if error.code and error.code >= 500:
            logging.error("HTTP %s: %s", error.code, error.description,
                          exc_info=error)
        return jsonify({
            "status": False,
            "message": error.description
        }), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Catches standard Python error (like ZeroDivisionError or Database down)"""
        ## Log the actual error for the developers
        logging.error(f"Unhandled Server Error: {str(error)}", exc_info=True)
        return jsonify({
            "status": False,
            "message": "An internal server error occured. Please try again later."
        }), 500