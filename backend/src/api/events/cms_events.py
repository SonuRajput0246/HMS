from sqlalchemy import event

from src.api.utils.datetime_helper import utcnow
from src.api.models.cms.table_zone_model import TableZone
from src.api.models.cms.table_model import Table
from src.api.models.cms.customer_model import Customer
from src.api.models.cms.recipe_category_model import RecipeCategory
from src.api.models.cms.recipe_model import Recipe
from src.api.models.cms.recipe_ingredient_model import RecipeIngredient
from src.api.models.cms.order_model import CMSOrder, CMSOrderItem, CMSPayment
from src.api.models.common.document_sequence_model import DocumentSequence


## Every CMS model in one place.
##
## The rest of the app registers a before_insert / before_update pair per model
## (see inventory_events.py, room_events.py, ...). Those listeners are not
## optional decoration: BaseModel.created_at / updated_at are nullable=False with
## no column default, so a row inserted without a listener raises
##   MySQLdb.IntegrityError (1048, "Column 'created_at' cannot be null")
## and `updated_at` silently stops advancing, plus deleted_at never gets set on a
## soft delete.
##
## Registering the same handler over a list keeps that guarantee in one place
## instead of nine copies, so adding a tenth CMS model is a one-line change
## rather than a new hand-written pair that someone can forget.
CMS_MODELS = [
    TableZone,
    Table,
    Customer,
    RecipeCategory,
    Recipe,
    RecipeIngredient,
    DocumentSequence,
    CMSOrder,
    CMSOrderItem,
    CMSPayment,
]


def _before_insert(mapper, connection, target):
    ## utcnow() is NAIVE on purpose. These are MySQL DATETIME columns, so the
    ## driver drops any offset anyway; writing naive keeps what Python holds
    ## identical to what the row holds, which means a later reload compares
    ## cleanly against a fresh utcnow().
    now = utcnow()
    target.created_at = now
    target.updated_at = now


def _before_update(mapper, connection, target):
    now = utcnow()
    target.updated_at = now

    ## Soft delete timestamp. Mirrors the existing per-model listeners: only set
    ## once, so an undelete-then-redelete cycle keeps the first timestamp rather
    ## than losing the original deletion time.
    if getattr(target, "is_deleted", False) and target.deleted_at is None:
        target.deleted_at = now


for _model in CMS_MODELS:
    event.listen(_model, "before_insert", _before_insert)
    event.listen(_model, "before_update", _before_update)