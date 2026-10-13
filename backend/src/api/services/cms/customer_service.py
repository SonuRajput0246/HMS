from sqlalchemy import func
from decimal import Decimal

from src.api.models.cms.customer_model import Customer
from src.api.services.common.document_sequence_service import DocumentSequenceService
from src.api.utils.responses import service_response


class CustomerService:
    def __init__(self, db):
        self.db = db
        self.sequence_service = DocumentSequenceService(db=db)

    def get_customers(self, data: dict):
        page_size = data.get("page_size", 20)
        page_number = data.get("page_number", 1)
        is_vip = data.get("is_vip")
        search_value = data.get("search_value")

        query = self.db.query(Customer).filter(Customer.is_deleted == False)

        if is_vip is not None:
            query = query.filter(Customer.is_vip == is_vip)

        if search_value:
            val = search_value.strip()
            ## Match name OR phone so the till can search with either. Phone is
            ## matched with a leading % because staff rarely remember the
            ## country code they dialled.
            like = f"%{val}%"
            query = query.filter(
                (Customer.name.like(f"%{val}%")) |
                (Customer.phone.like(like)) |
                (Customer.customer_code.like(f"{val}%"))
            )

        total_records = query.count()
        customers = (
            query
            .order_by(Customer.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )

        last_page = (total_records + page_size - 1) // page_size
        return {
            "status": True,
            "data": [self._serialize_customer(c) for c in customers],
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200

    def get_customer_by_id(self, customer_id: int):
        customer = self.db.query(Customer).filter_by(is_deleted=False, id=customer_id).first()
        if not customer:
            return service_response(False, "Customer not found", None, 404)

        return service_response(
            True, "Customer fetched successfully.", self._serialize_customer(customer), 200
        )

    def lookup_by_phone(self, phone: str):
        """Till-side lookup before opening an order.

        Returns the most recent match for the phone. Ties on the same phone are
        common (shared family number), so newest-wins is the least surprising
        behaviour for the operator.
        """
        val = (phone or "").strip()
        if not val:
            return service_response(False, "Phone number is required.", None, 400)

        customer = (
            self.db.query(Customer)
            .filter(Customer.is_deleted == False, Customer.phone == val)
            .order_by(Customer.id.desc())
            .first()
        )
        if not customer:
            return service_response(False, "No customer found for this phone number.", None, 404)

        return service_response(
            True, "Customer fetched successfully.", self._serialize_customer(customer), 200
        )

    def quick_create_customer(self, data: dict):
        """Minimal walk-in capture from the till.

        Name + phone only, and a duplicate phone is returned rather than
        rejected: the operator still needs to seat the guest, and the existing
        customer is the correct one to bill anyway.
        """
        phone = data["phone"]
        name = data["name"]

        existing = (
            self.db.query(Customer)
            .filter(Customer.is_deleted == False, Customer.phone == phone)
            .order_by(Customer.id.desc())
            .first()
        )
        if existing:
            return service_response(
                True,
                "Customer already exists for this phone number.",
                self._serialize_customer(existing),
                200
            )

        customer = Customer(
            customer_code=self.sequence_service.generate("customer"),
            name=name,
            phone=phone,
            is_active=True
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)

        return service_response(
            True, "Customer created successfully.", self._serialize_customer(customer), 201
        )

    def upsert_customer(self, data: dict):
        customer_id = data["id"]
        phone = data["phone"]
        is_deleted_op = data.get("is_deleted") is True

        if not is_deleted_op:
            ## A phone is the identity a customer is recognised by at the till,
            ## so two active customers cannot share one.
            duplicate = self.db.query(Customer).filter(
                Customer.is_deleted == False,
                Customer.phone == phone,
                Customer.id != customer_id
            ).first()
            if duplicate:
                return service_response(
                    False,
                    "Another active customer already uses this phone number.",
                    None, 409
                )

        if customer_id == 0:
            required_fields = ("name", "phone", "is_active")
            for field in required_fields:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required.", None, 400)

            customer = Customer(
                customer_code=self.sequence_service.generate("customer")
            )
            self.db.add(customer)
            message = "Customer created successfully."
            status_code = 201
        else:
            customer = self.db.query(Customer).filter_by(is_deleted=False, id=customer_id).first()
            if not customer:
                return service_response(False, "Customer not found", None, 404)
            message = "Customer updated successfully."
            status_code = 200

        fields = ("name", "phone", "email", "address", "dietary_notes", "is_vip", "is_active")
        for field in fields:
            if field in data:
                setattr(customer, field, data[field])

        ## Orders keep a FK to the customer, so the row must survive a delete.
        ## Marking it inactive (not deleted) hides it from the pickers while
        ## keeping historical orders readable.
        if is_deleted_op:
            customer.is_deleted = True
            customer.is_active = False
            message = "Customer deleted successfully."

        self.db.commit()
        self.db.refresh(customer)

        return service_response(
            True, message, self._serialize_customer(customer), status_code
        )

    def redeem_points(self, data: dict):
        """Spend loyalty points.

        The points are not converted to money here -- the caller decides what
        they are worth and applies it as an order discount. This only debits
        the balance so the two cannot drift apart.
        """
        customer_id = data["id"]
        points = data["points"]

        customer = self.db.query(Customer).filter_by(is_deleted=False, id=customer_id).first()
        if not customer:
            return service_response(False, "Customer not found", None, 404)

        if not customer.redeem_points(points):
            return service_response(
                False,
                f"Customer has only {customer.loyalty_points} loyalty points available.",
                None, 409
            )

        self.db.commit()
        self.db.refresh(customer)

        return service_response(
            True,
            "Loyalty points redeemed successfully.",
            self._serialize_customer(customer),
            200
        )

    ## ------------------------------------------------------------------
    ## internals
    ## ------------------------------------------------------------------

    def _serialize_customer(self, customer: Customer) -> dict:
        return {
            "id": customer.id,
            "customer_code": customer.customer_code,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "loyalty_points": customer.loyalty_points,
            "total_visits": customer.total_visits,
            "total_spent": str(customer.total_spent),
            "last_visit_at": customer.last_visit_at.isoformat() if customer.last_visit_at else None,
            "dietary_notes": customer.dietary_notes,
            "is_vip": customer.is_vip,
            "is_active": customer.is_active,
            "tier": customer.get_tier()
        }