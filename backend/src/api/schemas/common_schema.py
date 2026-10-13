from marshmallow import fields, validate
from src.api.schemas.base import BaseSchema
from src.api.schemas.id_schema import id_schema_factory


class GetAllCountriesSchema(BaseSchema):
    search_value = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0)
    )


GetStateCountryIdSchema = id_schema_factory("country_id", "Country Id")

class GetAllStatesSchema(GetStateCountryIdSchema):
    search_value = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0)
    )

GetCityStateIdSchema = id_schema_factory("state_id", "State Id")

class GetAllCitiesSchema(GetCityStateIdSchema):
    search_value = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0)
    )


class GetAllCurrenciesSchema(BaseSchema):
    search_value = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(min=0)
    )



class GetEnumOptionsSchema(BaseSchema):
    enum_key = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Length(min=1, max=100),
    )