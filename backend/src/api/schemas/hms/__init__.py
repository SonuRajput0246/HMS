"""HMS layer (schemas).

Do NOT import every module here. Several modules import each other and some
reach into models that reference back, so eager imports create cycles.

Import the specific module you need directly:

    from src.api.schemas.hms.room_schema import RoomSchema

Bucket layout mirrors src/api/models:
  common/  reachable from both instance trees
  hms/     hotel only
  cms/     cafe only

Bucket membership was derived from which blueprint gate in app.py reaches the
module through the import graph, not from its filename.
"""
