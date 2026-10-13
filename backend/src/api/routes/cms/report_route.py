from flask import Blueprint, request, jsonify

from src.api.middlewares.authorization import SELF_SERVICE, requires_module
from src.api.schemas.cms.report_schema import (
    CustomerReportSchema,
    DailyTrendReportSchema,
    ItemSalesReportSchema,
    KitchenReportSchema,
    SalesSummaryReportSchema,
    VoidReportSchema,
)
from src.api.services.cms.reports_service import ReportsService, ReportRangeError
from src.api.services.cms.kitchen_report_service import KitchenReportService
from src.api.services.cms.customer_report_service import CustomerReportService
from src.database.session import db_session


report_bp = Blueprint("report", __name__)


class ReportRoute:
    def __init__(self, reports_service, kitchen_report_service, customer_report_service):
        self.reports = reports_service
        self.kitchen = kitchen_report_service
        self.customers = customer_report_service

    def get_sales_summary(self):
        payload = request.get_json() or {}
        data = SalesSummaryReportSchema().load(payload)
        result, status_code = self._run(self.reports.get_sales_summary, data)
        return jsonify(result), status_code

    def get_item_sales(self):
        payload = request.get_json() or {}
        data = ItemSalesReportSchema().load(payload)
        result, status_code = self._run(self.reports.get_item_sales, data)
        return jsonify(result), status_code

    def get_daily_trend(self):
        payload = request.get_json() or {}
        data = DailyTrendReportSchema().load(payload)
        result, status_code = self._run(self.reports.get_daily_trend, data)
        return jsonify(result), status_code

    def get_void_report(self):
        payload = request.get_json() or {}
        data = VoidReportSchema().load(payload)
        result, status_code = self._run(self.reports.get_void_report, data)
        return jsonify(result), status_code

    def get_kitchen_performance(self):
        payload = request.get_json() or {}
        data = KitchenReportSchema().load(payload)
        result, status_code = self._run(self.kitchen.get_prep_performance, data)
        return jsonify(result), status_code

    def get_customer_report(self):
        payload = request.get_json() or {}
        data = CustomerReportSchema().load(payload)
        result, status_code = self._run(self.customers.get_customer_report, data)
        return jsonify(result), status_code

    @staticmethod
    def _run(method, data):
        """Report methods translate a bad window into ReportRangeError; turn
        that into a clean 400 instead of letting it surface as a 500."""
        try:
            return method(data)
        except ReportRangeError as exc:
            return {
                "status": False,
                "message": str(exc),
                "data": None
            }, 400


reports_service_instance = ReportsService(db=db_session)
kitchen_report_service_instance = KitchenReportService(db=db_session)
customer_report_service_instance = CustomerReportService(db=db_session)

report_route = ReportRoute(
    reports_service=reports_service_instance,
    kitchen_report_service=kitchen_report_service_instance,
    customer_report_service=customer_report_service_instance
)


report_bp.add_url_rule('/sales-summary', view_func=requires_module("REPORTS")(report_route.get_sales_summary), methods=['POST'])
report_bp.add_url_rule('/item-sales', view_func=requires_module("REPORTS")(report_route.get_item_sales), methods=['POST'])
report_bp.add_url_rule('/daily-trend', view_func=requires_module("REPORTS")(report_route.get_daily_trend), methods=['POST'])
report_bp.add_url_rule('/void-report', view_func=requires_module("REPORTS")(report_route.get_void_report), methods=['POST'])
report_bp.add_url_rule('/kitchen-performance', view_func=requires_module("REPORTS")(report_route.get_kitchen_performance), methods=['POST'])
report_bp.add_url_rule('/customer-report', view_func=requires_module("REPORTS")(report_route.get_customer_report), methods=['POST'])