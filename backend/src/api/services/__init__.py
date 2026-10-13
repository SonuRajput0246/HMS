"""Service layer.

Do NOT import every module here. Several services import each other and some
reach into models that reference back, so eager imports create cycles.

Import the specific module you need directly:

    from src.api.services.common_service import CommonService

Routes construct these; services own the database work and are the only layer
that should be talking to SQL directly.
"""