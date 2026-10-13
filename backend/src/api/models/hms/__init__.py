"""HMS models.

Do NOT eagerly import every module here. Several models reference each other
(`relationship()` back-references), so importing them all creates circular
imports. Import the specific model you need directly:

    from src.api.models.hms.room_model import Room

Base model discovery happens in src/api/models/__init__.py, which imports every
model module so SQLAlchemy's declarative registry knows all mapped classes
before create_all()/migrations run.
"""
