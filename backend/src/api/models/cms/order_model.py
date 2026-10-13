from decimal import Decimal
from datetime import datetime

from src.api.utils.datetime_helper import elapsed_minutes, utcnow
from sqlalchemy import String, Numeric, Text, ForeignKey, DateTime, Integer, Enum as SqlEnum, Index, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base_model import BaseModel
from typing import TYPE_CHECKING, List, Optional
import enum

if TYPE_CHECKING:
    from src.api.models.cms.table_model import Table
    from src.api.models.cms.customer_model import Customer
    from src.api.models.cms.recipe_model import Recipe
    from src.api.models.common.inventory_model import Inventory
    from src.api.models.common.user_model import User


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class OrderTypeEnum(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class PaymentStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentMethodEnum(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    WALLET = "wallet"
    SPLIT = "split"


## Order item prep states, as stored in cms_order_items.prep_status.
## Plain strings rather than a DB enum, so adding a state is code-only.
PREP_PENDING = "pending"
PREP_PREPARING = "preparing"
PREP_READY = "ready"
PREP_VOIDED = "voided"

PREP_STATUSES = [PREP_PENDING, PREP_PREPARING, PREP_READY, PREP_VOIDED]

## States a KDS chef may set by hand. 'voided' is excluded: voiding a line is a
## cashier action that needs a reason, handled by OrderService.void_item.
PREP_STATUS_SETTABLE = [PREP_PENDING, PREP_PREPARING, PREP_READY]


class CMSOrder(BaseModel):
    __tablename__ = "cms_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    
    # Flexible reference: table, customer, or walkin
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'table', 'customer', 'walkin'
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    
    status: Mapped[OrderStatusEnum] = mapped_column(SqlEnum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PENDING)
    order_type: Mapped[OrderTypeEnum] = mapped_column(SqlEnum(OrderTypeEnum), nullable=False, default=OrderTypeEnum.DINE_IN)
    
    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    
    # Payment
    payment_status: Mapped[PaymentStatusEnum] = mapped_column(SqlEnum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    kitchen_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_ready_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    table: Mapped[Optional["Table"]] = relationship("Table", back_populates="orders", foreign_keys=[table_id])
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="orders", foreign_keys=[customer_id])
    items: Mapped[List["CMSOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[List["CMSPayment"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_cms_order_subtotal_nonneg"),
        CheckConstraint("tax_amount >= 0", name="ck_cms_order_tax_nonneg"),
        CheckConstraint("discount_amount >= 0", name="ck_cms_order_discount_nonneg"),
        CheckConstraint("total_amount >= 0", name="ck_cms_order_total_nonneg"),
        CheckConstraint("paid_amount >= 0", name="ck_cms_order_paid_nonneg"),
        CheckConstraint("discount_amount <= subtotal + tax_amount", name="ck_cms_order_discount_valid"),
        
        Index("ix_cms_order_reference", "is_deleted", "reference_type", "reference_id"),
        Index("ix_cms_order_status", "is_deleted", "status", "id"),
        Index("ix_cms_order_payment_status", "is_deleted", "payment_status", "id"),
        Index("ix_cms_order_table", "is_deleted", "table_id", "id"),
        Index("ix_cms_order_customer", "is_deleted", "customer_id", "id"),
        Index("ix_cms_order_ordered_at", "is_deleted", "ordered_at", "id"),
        Index("ix_cms_order_number", "is_deleted", "order_number"),
    )

    def __repr__(self):
        return f"CMSOrder(id={self.id}, order_number={self.order_number}, status={self.status})"

    def get_reference_label(self) -> str:
        if self.reference_type == "table" and self.table:
            return f"Table {self.table.table_number}"
        elif self.reference_type == "customer" and self.customer:
            return f"Customer: {self.customer.name}"
        return f"Walk-in #{self.order_number}"

    def calculate_totals(self) -> None:
        """Recompute subtotal and total from the live line items.

        Each line's total_price is recalculated from quantity x unit_price
        rather than trusted as-is. Doing it here means the order header cannot
        drift from its own lines: a caller that sets quantity without also
        updating total_price still produces a correct bill, and the persisted
        line row stays consistent with what was summed.
        """
        subtotal = Decimal("0.00")
        for item in self.items:
            if item.is_deleted:
                continue
            item.calculate_total()
            subtotal += item.total_price

        self.subtotal = subtotal
        self.total_amount = (
            subtotal
            + (self.tax_amount or Decimal("0.00"))
            - (self.discount_amount or Decimal("0.00"))
        )

    def update_payment_status(self) -> None:
        paid = self.paid_amount or Decimal("0.00")
        total = self.total_amount or Decimal("0.00")

        if paid <= 0:
            self.payment_status = PaymentStatusEnum.PENDING
        elif paid >= total:
            self.payment_status = PaymentStatusEnum.PAID
        else:
            self.payment_status = PaymentStatusEnum.PARTIAL

    def is_fully_paid(self) -> bool:
        return self.payment_status == PaymentStatusEnum.PAID

    def due_amount(self) -> Decimal:
        """Outstanding balance, never negative."""
        return max(
            (self.total_amount or Decimal("0.00")) - (self.paid_amount or Decimal("0.00")),
            Decimal("0.00")
        )

    def can_be_cancelled(self) -> bool:
        return self.status in (OrderStatusEnum.PENDING, OrderStatusEnum.CONFIRMED)

    def cancel(self, reason: str, user_id: int) -> None:
        if not self.can_be_cancelled():
            raise ValueError(f"Order in status {self.status} cannot be cancelled")
        self.status = OrderStatusEnum.CANCELLED
        self.cancelled_at = utcnow()
        self.cancelled_reason = reason
        self.updated_by = user_id
        # Free table if linked
        if self.table and self.table.status == "occupied":
            self.table.free()

    def confirm(self) -> None:
        if self.status != OrderStatusEnum.PENDING:
            raise ValueError("Only pending orders can be confirmed")
        self.status = OrderStatusEnum.CONFIRMED
        self.confirmed_at = utcnow()

    def start_preparing(self) -> None:
        if self.status != OrderStatusEnum.CONFIRMED:
            raise ValueError("Only confirmed orders can start preparing")
        self.status = OrderStatusEnum.PREPARING

    def mark_ready(self) -> None:
        if self.status != OrderStatusEnum.PREPARING:
            raise ValueError("Only preparing orders can be marked ready")
        self.status = OrderStatusEnum.READY

    def serve(self) -> None:
        if self.status != OrderStatusEnum.READY:
            raise ValueError("Only ready orders can be served")
        self.status = OrderStatusEnum.SERVED

    def complete(self) -> None:
        if not self.is_fully_paid():
            raise ValueError("Order must be fully paid before completion")
        self.status = OrderStatusEnum.COMPLETED
        self.completed_at = utcnow()
        # Free table if linked
        if self.table and self.table.status == "occupied":
            self.table.free()
        # Record customer visit
        if self.customer:
            self.customer.record_visit(self.total_amount)


class CMSOrderItem(BaseModel):
    __tablename__ = "cms_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("cms_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Item source: recipe or inventory
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'recipe', 'inventory'
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Denormalized
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1.00"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    
    # Modifiers & customizations
    modifiers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cooking_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    spice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # mild, medium, hot, extra_hot
    
    # Kitchen/Prep tracking
    prep_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PREP_PENDING, server_default=PREP_PENDING
    )  # pending | preparing | ready | voided
    ## Copied from the recipe at order time so a later station change does not
    ## reroute a ticket already sitting in the kitchen.
    station: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prep_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    prep_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ## Void audit. A voided line is money that was almost taken and a possible
    ## staff-discipline issue, so the loss report needs to answer who removed
    ## what, when, and why -- not just infer it from a shrinking total.
    ##
    ## Kept as real columns rather than the earlier trick of prefixing
    ## cooking_instructions with "[VOIDED: ...]": that put the reason somewhere
    ## no report could filter or aggregate on, and mixed audit text into a field
    ## the kitchen legitimately reads for the dish instructions.
    void_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Recipe/Inventory links for reference
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    order: Mapped["CMSOrder"] = relationship(back_populates="items")
    recipe: Mapped[Optional["Recipe"]] = relationship("Recipe", foreign_keys=[recipe_id])
    inventory_item: Mapped[Optional["Inventory"]] = relationship("Inventory", foreign_keys=[inventory_item_id])
    voided_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[voided_by])

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cms_order_item_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_cms_order_item_unit_price_nonneg"),
        CheckConstraint("total_price >= 0", name="ck_cms_order_item_total_nonneg"),
        
        Index("ix_cms_order_item_order", "is_deleted", "order_id", "id"),
        Index("ix_cms_order_item_prep", "is_deleted", "order_id", "prep_status", "station"),
        Index("ix_cms_order_item_recipe", "is_deleted", "recipe_id"),
        Index("ix_cms_order_item_inventory", "is_deleted", "inventory_item_id"),
        ## Drives the void / loss report: scan voided lines in a date window
        ## ordered by when they were removed. Leading is_deleted keeps the
        ## soft-deleted voided lines (which is all of them) in one range scan.
        Index("ix_cms_order_item_void", "is_deleted", "voided_at", "voided_by"),
    )

    def __repr__(self):
        return f"CMSOrderItem(id={self.id}, order_id={self.order_id}, item={self.item_name}, qty={self.quantity})"

    def calculate_total(self) -> None:
        self.total_price = self.quantity * self.unit_price

    def start_prep(self) -> None:
        if self.prep_status != PREP_PENDING:
            raise ValueError(f"Item prep cannot start from '{self.prep_status}'.")
        self.prep_status = PREP_PREPARING
        self.prep_started_at = utcnow()

    def complete_prep(self) -> None:
        if self.prep_status != PREP_PREPARING:
            raise ValueError(
                f"Item is '{self.prep_status}', not 'preparing', so it cannot be marked ready."
            )
        self.mark_ready()

    def mark_ready(self) -> None:
        """Jump straight to ready.

        Allowed from pending as well as preparing: many KDS screens are one-tap
        ("tap when it leaves the pass"), and forcing a tap-to-start first
        doubles the taps for every dish. prep_started_at is stamped when it was
        never set so the elapsed-time maths stays honest.
        """
        if self.prep_status == PREP_READY:
            raise ValueError("Item is already ready.")
        if self.prep_status == PREP_VOIDED:
            raise ValueError("A voided item cannot be marked ready.")

        now = utcnow()
        if self.prep_started_at is None:
            self.prep_started_at = now
        self.prep_status = PREP_READY
        self.prep_completed_at = now

    def void_prep(self) -> None:
        self.prep_status = PREP_VOIDED

    def is_voided(self) -> bool:
        return self.prep_status == PREP_VOIDED

    def is_ready(self) -> bool:
        return self.prep_status == PREP_READY

    def is_in_kitchen_queue(self) -> bool:
        """Still needs kitchen attention: not plated, not voided."""
        return self.prep_status in (PREP_PENDING, PREP_PREPARING)

    def minutes_in_prep(self) -> int | None:
        """Whole minutes since prep began, or None if it never started."""
        return elapsed_minutes(self.prep_started_at)

    def minutes_since_ordered(self, ordered_at: datetime | None = None) -> int | None:
        """Whole minutes since the order was placed.

        Falls back to the order's ordered_at because an unstarted item has no
        prep_started_at, and "how long has this ticket been waiting" is the
        number the chef actually needs.
        """
        if ordered_at is None:
            ordered_at = self.order.ordered_at if self.order else None
        return elapsed_minutes(ordered_at)

    def is_recipe_item(self) -> bool:
        return self.item_type == "recipe"

    def is_inventory_item(self) -> bool:
        return self.item_type == "inventory"


class CMSPayment(BaseModel):
    __tablename__ = "cms_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("cms_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethodEnum] = mapped_column(SqlEnum(PaymentMethodEnum), nullable=False)
    payment_status: Mapped[PaymentStatusEnum] = mapped_column(SqlEnum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING)
    
    # Split bill support
    split_group_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    split_payer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Gateway / external reference
    transaction_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gateway_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Verification
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    order: Mapped["CMSOrder"] = relationship(back_populates="payments")
    verified_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[verified_by])
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cms_payment_amount_positive"),
        
        Index("ix_cms_payment_order", "is_deleted", "order_id", "id"),
        Index("ix_cms_payment_status", "is_deleted", "payment_status", "id"),
        Index("ix_cms_payment_method", "is_deleted", "payment_method", "id"),
        Index("ix_cms_payment_split_group", "is_deleted", "split_group_id"),
        Index("ix_cms_payment_paid_at", "is_deleted", "paid_at", "id"),
    )

    def __repr__(self):
        return f"CMSPayment(id={self.id}, order_id={self.order_id}, amount={self.amount}, method={self.payment_method})"

    def mark_success(self, transaction_ref: str | None = None, verified_by: int | None = None) -> None:
        self.payment_status = PaymentStatusEnum.PAID
        self.paid_at = utcnow()
        if transaction_ref:
            self.transaction_ref = transaction_ref
        if verified_by:
            self.verified_by = verified_by
            self.verified_at = utcnow()

    def mark_failed(self) -> None:
        self.payment_status = PaymentStatusEnum.FAILED
        self.paid_at = None

    def is_split_payment(self) -> bool:
        return self.split_group_id is not None