"""Common layer (services).

Do NOT import every module here. Several modules import each other and some
reach into models that reference back, so eager imports create cycles.

Import the specific module you need directly:

    from src.api.services.common.common_service import CommonService

Bucket layout mirrors src/api/models:
  common/  shared infrastructure, reachable from the hotel tree
  hms/     the hotel domain

app.py registers every blueprint unconditionally, so membership is decided
by what app.py imports and mounts.
"""
