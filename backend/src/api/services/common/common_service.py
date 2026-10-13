from src.api.models import LoginSliders, Country, State, City, Currency, EnumDefinition, EnumOption
from src.api.utils.responses import service_response
from src.config import get_config

config = get_config()

## Derived from DATABASE_URL rather than a separate DB_NAME setting, because
## .env in this project points at one database by URL and has no DB_NAME
## attribute on the config object.


class CommonService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def get_instance_config():
        """Which product this backend is running as.

        Public and unauthenticated on purpose: the frontend calls it during
        APP_INITIALIZER, before any token exists. It exposes only the instance
        discriminator and the database name -- no host, no credentials, no rows.
        A login screen cannot leak anything useful from it.

        The point is to make the backend the single source of truth for which
        instance is live. Previously the frontend read `instance_type` from its
        own config.json and the backend read `INSTANCE_TYPE` from .env, and
        nothing compared them: a mismatch produced no error at all, just a
        frontend serving URLs whose endpoints did not exist.
        """
        return {
            "status": True,
            "message": "Instance configuration fetched successfully.",
            "data": {
                "instance_type": config.INSTANCE_TYPE.value
            },
        }, 200


    def get_login_slider_data(self):
        sliders = (
            self.db.query(LoginSliders)
            .filter(
                LoginSliders.is_active == True,
                LoginSliders.is_deleted == False
            )
            .order_by(LoginSliders.display_order.asc())
            .all()
        )
        if not sliders:
            return {"status": True, "message": "Sliders data not found"}, 404

        return {
            "status": True,
            "data": [
                {
                    "id": slider.id,
                    "title": slider.title,
                    "image_path": slider.image_path,
                    "alt_text": slider.alt_text,
                    "display_order": slider.display_order
                }
                for slider in sliders
            ]
        }, 200


    def get_all_countries_list(self, data:dict):
        search_value = data.get("search_value")
        query = self.db.query(Country)
        if search_value:
            val = search_value.strip()
            query = query.filter(Country.name.like(f"{val}%"))

        countries = query.all()
        countries_list = [
            {
                "id": country.id,
                "name": country.name,
                "nationality": country.nationality
            }
            for country in countries
        ]

        return {
            "status": True,
            "data": countries_list
        }, 200


    def get_all_states_list(self, data:dict):
        country_id = data["country_id"]
        search_value = data.get("search_value")
        query = self.db.query(State).filter(State.country_id == country_id)
        if search_value:
            val = search_value.strip()
            query = query.filter(Country.name.like(f"{val}%"))

        states = query.all()
        states_list = [
            {
                "id": state.id,
                "country_id": state.country_id,
                "name": state.name
            }
            for state in states
        ]

        return {
            "status": True,
            "data": states_list
        }, 200


    def get_all_cities_list(self, data:dict):
        state_id = data["state_id"]
        search_value = data.get("search_value")
        query = self.db.query(City).filter(City.state_id == state_id)
        if search_value:
            val = search_value.strip()
            query = query.filter(City.name.like(f"{val}%"))

        cities = query.all()
        cities_list = [
            {
                "id": city.id,
                "state_id": city.state_id,
                "name": city.name
            }
            for city in cities
        ]

        return {
            "status": True,
            "data": cities_list
        }, 200


    def get_all_currencies_list(self, data: dict):
        search_value = data.get("search_value")
        query = self.db.query(Currency).filter_by(is_active=True)
        if search_value:
            val = search_value.strip()
            query = query.filter(Currency.code.like(f"{val}%"))

        currencies = query.all()
        currencies_list = [
            {
                "code": currency.code
            }
            for currency in currencies
        ]

        return {
            "status": True,
            "data": currencies_list
        }, 200

    def get_enum_options(self, data: dict):
        """Active options for one enum definition, for populating a dropdown.

        Generic on purpose: every enum-backed column in the app (room_status,
        payment_type, payment_method, ...) reads through here, so adding an
        option is a data change and never a frontend edit.
        """
        enum_key = data.get("enum_key")

        definition = (
            self.db.query(EnumDefinition)
            .filter(
                EnumDefinition.enum_key == enum_key,
                EnumDefinition.is_deleted == False,
            )
            .first()
        )

        if not definition:
            return service_response(False, f"Unknown enum_key '{enum_key}'.", None, 404)

        options = (
            self.db.query(EnumOption)
            .filter(
                EnumOption.enum_id == definition.id,
                EnumOption.is_deleted == False,
                EnumOption.is_active == True,
            )
            .order_by(EnumOption.sort_order.asc())
            .all()
        )

        ## 'is_default' included so a UI can preselect, and the option key is
        ## the exact string that must be written back to the backing column -
        ## EnumService validates incoming values against these same rows.
        return service_response(
            True,
            "Enum options fetched successfully.",
            [
                {
                    "option_key": option.option_key,
                    "option_label": option.option_label,
                    ## Material icon name for options that define one (e.g. the
                    ## template_channel options). Null for enums that do not use
                    ## icons, so consumers must handle a missing glyph rather
                    ## than assume one is present.
                    "icon": option.icon,
                    "sort_order": option.sort_order,
                    "is_default": option.is_default,
                }
                for option in options
            ],
            200,
        )