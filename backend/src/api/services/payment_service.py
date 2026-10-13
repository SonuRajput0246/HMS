import logging
from datetime import datetime
from decimal import Decimal

from src.api.models import Payment, SystemSetting
from src.api.models.enum_definitions_model import EnumDefinition
from src.api.services.exchange_service import ExchangeService
from src.api.utils.currency_utils import calculate_base_amount
from src.api.utils.responses import service_response


logger = logging.getLogger(__name__)

## `enum_definitions.enum_key` values backing the two enum-backed columns on
## `payments`. Seeded by enum_seeder.py.
PAYMENT_TYPE_ENUM_KEY = "payment_type"
PAYMENT_STATUS_ENUM_KEY = "payment_status"

## Always accepted, whatever the enum table says. `advance` drives the
## one-advance-per-reservation rule below, and `refunded` is written by
## refund_events.apply_refund_effect, so neither may be lost to a bad seed or
## to an admin toggling an option off.
CORE_PAYMENT_TYPES = ("advance", "additional_advance", "partial", "full", "refund")
CORE_PAYMENT_STATUSES = ("pending", "success", "failed", "refunded")


class PaymentService:
    def __init__(self, db):
        self.db = db
        self._enum_cache: dict[str, tuple[str, ...]] = {}


    def insert_payment_details(self, data: dict):
        ## `.get` rather than `data[...]`: a missing key used to raise KeyError
        ## inside the service, which the route surfaced as a 500 rather than a
        ## validation failure.
        reservation_id = data.get("reservation_id")

        if not reservation_id:
            return service_response(False, "Field reservation_id is required", None, 400)

        payment_type = self._normalise(
            data.get("payment_type"), PAYMENT_TYPE_ENUM_KEY, CORE_PAYMENT_TYPES
        )
        if payment_type is None:
            return service_response(
                False,
                f"Unknown payment_type '{data.get('payment_type')}'. Allowed values: "
                + ", ".join(self._valid_values(PAYMENT_TYPE_ENUM_KEY, CORE_PAYMENT_TYPES))
                + ".",
                None,
                400,
            )

        payment_status = self._normalise(
            data.get("payment_status"), PAYMENT_STATUS_ENUM_KEY, CORE_PAYMENT_STATUSES
        )
        if payment_status is None:
            return service_response(
                False,
                f"Unknown payment_status '{data.get('payment_status')}'. Allowed values: "
                + ", ".join(self._valid_values(PAYMENT_STATUS_ENUM_KEY, CORE_PAYMENT_STATUSES))
                + ".",
                None,
                400,
            )

        # Only the first advance is unique per reservation. Every other type
        # is a repeatable follow-up -- the booking collects one advance at
        # prime, then the guest settles in instalments, so rejecting a
        # second `additional_advance` (as a blanket per-type uniqueness
        # check does) makes it impossible to actually collect anything.
        #
        # Soft-deleted rows are excluded: a voided advance has not been
        # collected, so it must not lock out re-recording one.
        if payment_type == "advance":
            duplicate_check = self.db.query(Payment).filter(
                Payment.reservation_id == reservation_id,
                Payment.payment_type == payment_type,
                Payment.is_deleted == False
            ).first()
            if duplicate_check:
                return service_response(
                    False,
                    "Advance payment already recorded for this reservation. "
                    "Record an additional advance instead.",
                    None,
                    409
                )

        REQUIRED_FIELDS = ("amount", "currency", "payment_method")
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                return service_response(False, f"Field {field} is required", None, 400)

        paid_at_str = data.get("paid_at")
        if paid_at_str:
            paid_at = datetime.fromisoformat(paid_at_str.replace("Z", "+00:00"))
        else:
            paid_at = None

        default_currency = self.db.query(SystemSetting).filter_by(key='default_currency').first()
        if not default_currency:
            to_currency = 'INR'
        else:
            to_currency = default_currency.value

        from_currency = data.get("currency")
        amount = Decimal(str(data['amount']))
        exchange_rate = ExchangeService.get_rate(from_currency, to_currency)
        base_amount = calculate_base_amount(amount, exchange_rate)

        payment = Payment(
            reservation_id=reservation_id,
            payment_type=payment_type,
            amount=amount,
            currency=from_currency,
            payment_method=data['payment_method'],
            payment_status=payment_status,
            transaction_ref=data.get('transaction_ref'),
            remarks=data.get('remark'),
            paid_at=paid_at,
            verified_by=1,
            exchange_rate=94.50,
            base_amount=base_amount
        )
        self.db.add(payment)
        self.db.commit()
        return service_response(True, "Payment recorded successfully.", None, 201)


    # ---------------------------------------------------------------
    # ENUM HELPERS
    # ---------------------------------------------------------------

    def _valid_values(self, enum_key: str, core: tuple[str, ...]) -> tuple[str, ...]:
        """Allowed values for an enum-backed column, read once per instance."""
        if enum_key not in self._enum_cache:
            self._enum_cache[enum_key] = self._load_values(enum_key, core)
        return self._enum_cache[enum_key]

    def _load_values(self, enum_key: str, core: tuple[str, ...]) -> tuple[str, ...]:
        """`enum_options` keys for one enum definition."""
        try:
            definition = (
                self.db.query(EnumDefinition)
                .filter(
                    EnumDefinition.enum_key == enum_key,
                    EnumDefinition.is_deleted == False,
                )
                .first()
            )

            keys = [
                str(option.option_key).strip().lower()
                for option in (definition.options if definition else [])
                if option.is_deleted == False and option.is_active
            ]
        except Exception:
            ## Never let a bad enum table stop a payment being recorded: fall
            ## back to the core values and log loudly.
            logger.exception(
                "PaymentService: could not read '%s' options. Falling back to %s.",
                enum_key, list(core),
            )
            keys = []

        ## Union, not replacement: a new option added to the enum table is
        ## accepted immediately, but deactivating a core option in the admin UI
        ## cannot block recording a payment.
        return tuple(dict.fromkeys([*keys, *core]))

    def _normalise(self, value, enum_key: str, core: tuple[str, ...]) -> str | None:
        """Bare value for the String column, or None when not an allowed option."""
        if value is None:
            return None

        text = str(getattr(value, "value", value)).strip().lower()
        if not text:
            return None

        return text if text in self._valid_values(enum_key, core) else None