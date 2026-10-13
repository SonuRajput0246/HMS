from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.common.template_schema import (
    GetTemplateByIdSchema,
    GetTemplateCodesSchema,
    GetTemplatesSchema,
    PreviewTemplateSchema,
    UpsertTemplateSchema,
)
from src.api.services.common.template_service import TemplateService
from src.database.session import db_session

template_bp = Blueprint('template', __name__)


class TemplateRoute:
    """HTTP layer for the template admin screens.

    Validation raises MarshmallowError, which is converted globally to
    {"status": false, "message": ...} with a 400 by
    src/api/utils/error_handlers.py.
    """

    def __init__(self, template_service):
        self.template_service = template_service


    def get_templates(self):
        payload = request.get_json(silent=True) or {}
        validated_data = GetTemplatesSchema().load(payload)
        result, status_code = self.template_service.get_templates(validated_data)
        return jsonify(result), status_code


    def get_template_by_id(self):
        payload = request.args.to_dict()
        validated_data = GetTemplateByIdSchema().load(payload)
        result, status_code = self.template_service.get_template_by_id(
            validated_data["id"]
        )
        return jsonify(result), status_code


    def get_template_codes(self):
        payload = request.args.to_dict()
        validated_data = GetTemplateCodesSchema().load(payload)
        result, status_code = self.template_service.get_template_codes(validated_data)
        return jsonify(result), status_code


    def upsert_template(self):
        payload = request.get_json(silent=True) or {}
        validated_data = UpsertTemplateSchema().load(payload)
        result, status_code = self.template_service.upsert_template(validated_data)
        return jsonify(result), status_code


    def preview_template(self):
        ## Nothing is persisted, so this is safe to call on every keystroke
        ## from the live-preview panel in the Angular editor.
        payload = request.get_json(silent=True) or {}
        validated_data = PreviewTemplateSchema().load(payload)
        result, status_code = self.template_service.preview_template(validated_data)
        return jsonify(result), status_code


template_service_instance = TemplateService(db=db_session)
template_route = TemplateRoute(template_service=template_service_instance)


template_bp.add_url_rule(
    '/get-templates',
    view_func=requires_module("TEMPLATE")(template_route.get_templates),
    methods=['POST']
)
template_bp.add_url_rule(
    '/get-template-by-id',
    view_func=requires_module("TEMPLATE")(template_route.get_template_by_id),
    methods=['GET']
)
template_bp.add_url_rule(
    '/get-template-codes',
    view_func=requires_module("TEMPLATE")(template_route.get_template_codes),
    methods=['GET']
)
template_bp.add_url_rule(
    '/upsert-template',
    view_func=requires_module("TEMPLATE")(template_route.upsert_template),
    methods=['POST']
)
template_bp.add_url_rule(
    '/preview-template',
    view_func=requires_module("TEMPLATE")(template_route.preview_template),
    methods=['POST']
)