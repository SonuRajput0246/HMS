import os

from .development import DevelopmentConfig
from .production import ProductionConfig

__all__ = ["get_config", "DevelopmentConfig", "ProductionConfig"]


def get_config():
    env = os.getenv("FLASK_ENV", "development")

    if env == "production":
        return ProductionConfig

    return DevelopmentConfig
