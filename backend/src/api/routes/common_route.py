from flask import request, jsonify, g, Blueprint

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.common_schema import GetAllStatesSchema, GetAllCountriesSchema, GetAllCitiesSchema, \
    GetAllCurrenciesSchema, GetEnumOptionsSchema
from src.api.services.common_service import CommonService
from src.api.services.tenant_service import TenantService
from src.database.session import db_session

common_bp = Blueprint('common', __name__)


class CommonRoute:
    def __init__(self, common_service, tenant_service):
        self.common_service = common_service
        self.tenant_service = tenant_service


    def get_login_slider_data(self):
        result, status_code = self.common_service.get_login_slider_data()
        return jsonify(result), status_code

    def get_tenant_info(self):
        ## g.tenant is set by the tenant resolver before this runs. It is None
        ## when the request named no tenant, which the service reports as a 404
        ## rather than serving some default hotel's branding.
        result, status_code = self.tenant_service.get_public_info(getattr(g, "tenant", None))
        return jsonify(result), status_code

    def get_all_countries(self):
        payload = request.get_json() or {}
        validated_data = GetAllCountriesSchema().load(payload)
        result, status_code = self.common_service.get_all_countries_list(validated_data)
        return jsonify(result), status_code

    def get_all_states(self):
        payload = request.get_json() or {}
        validated_data = GetAllStatesSchema().load(payload)
        result, status_code = self.common_service.get_all_states_list(validated_data)
        return jsonify(result), status_code

    def get_all_cities(self):
        payload = request.get_json() or {}
        validated_data = GetAllCitiesSchema().load(payload)
        result, status_code = self.common_service.get_all_cities_list(validated_data)
        return jsonify(result), status_code

    def get_all_currencies(self):
        payload = request.get_json() or {}
        validated_data = GetAllCurrenciesSchema().load(payload)
        result, status_code = self.common_service.get_all_currencies_list(validated_data)
        return jsonify(result), status_code

    def get_enum_options(self):
        payload = request.get_json() or {}
        validated_data = GetEnumOptionsSchema().load(payload)
        result, status_code = self.common_service.get_enum_options(validated_data)
        return jsonify(result), status_code

common_service_instance = CommonService(db=db_session)
tenant_service_instance = TenantService(db=db_session)
common_route = CommonRoute(common_service=common_service_instance, tenant_service=tenant_service_instance)
## Public. The frontend fetches this during APP_INITIALIZER, before any token
## exists, so jwt_required would deadlock the boot sequence.
common_bp.add_url_rule('/get-login-slider-data', view_func=common_route.get_login_slider_data, methods=['GET'])
## Public for the same reason, and it is how the frontend learns which hotel its
## subdomain points at so the login page can show the right name.
common_bp.add_url_rule('/tenant-info', view_func=common_route.get_tenant_info, methods=['GET'])
common_bp.add_url_rule('/get-all-countries', view_func=requires_module(SELF_SERVICE)(common_route.get_all_countries), methods=['POST'])
common_bp.add_url_rule('/get-all-states', view_func=requires_module(SELF_SERVICE)(common_route.get_all_states), methods=['POST'])
common_bp.add_url_rule('/get-all-cities', view_func=requires_module(SELF_SERVICE)(common_route.get_all_cities), methods=['POST'])
common_bp.add_url_rule('/get-all-currencies', view_func=requires_module(SELF_SERVICE)(common_route.get_all_currencies), methods=['POST'])
common_bp.add_url_rule('/get-enum-options', view_func=requires_module(SELF_SERVICE)(common_route.get_enum_options), methods=['POST'])
