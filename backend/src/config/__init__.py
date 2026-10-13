import os

from .base import InstanceType
from .development import DevelopmentConfig
from .production import ProductionConfig

__all__ = ["get_config", "InstanceType", "DevelopmentConfig", "ProductionConfig"]


def get_config():
    env = os.getenv("FLASK_ENV", "development")

    if env == "production":
        return ProductionConfig

    return DevelopmentConfig
