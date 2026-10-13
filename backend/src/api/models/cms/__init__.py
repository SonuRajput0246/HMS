"""CMS-specific models package.

Do NOT eagerly import all CMS models here. Order models reference
recipes/inventory/tables/customers, and those models reference back
(order -> table.orders, recipe.ingredients). Importing them all eagerly
creates circular imports.

Import the specific model you need directly, e.g.:

    from src.api.models.cms.order_model import CMSOrder
    from src.api.models.cms.table_model import Table
    from src.api.models.cms.customer_model import Customer
    from src.api.models.cms.recipe_model import Recipe

Base model discovery happens in src/api/models/__init__.py which must
import all model modules so SQLAlchemy's declarative registry knows
about every mapped class before create_all()/migrations run.
"""