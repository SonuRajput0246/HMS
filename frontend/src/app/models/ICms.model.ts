/**
 * CMS (Cafe Management System) contracts.
 *
 * Mirrors the Flask schemas in src/api/schemas/cms/. Field names match the API
 * exactly -- the backend is snake_case throughout and nothing here is renamed,
 * because a mapping layer would be one more thing to keep in sync.
 *
 * Money arrives as a STRING, never a number. The backend returns Decimal
 * columns as `str(...)` deliberately: 0.1 + 0.2 !== 0.3 in IEEE-754, and a POS
 * that displays a wrong total is worse than one that shows "0.30" twice. Use
 * `toAmount()` before any arithmetic.
 */

export type OrderStatus =
  | 'pending' | 'confirmed' | 'preparing' | 'ready'
  | 'served' | 'cancelled' | 'completed';

export type PaymentStatus = 'pending' | 'partial' | 'paid' | 'refunded' | 'failed';

export type PaymentMethod = 'cash' | 'card' | 'upi' | 'wallet' | 'split';

export type OrderType = 'dine_in' | 'takeaway' | 'delivery';

export type TableStatus = 'available' | 'occupied' | 'reserved' | 'cleaning' | 'maintenance';

/** Order-line kitchen state. `voided` is server-set, never sent by the KDS. */
export type PrepStatus = 'pending' | 'preparing' | 'ready' | 'voided';

export type SpiceLevel = 'none' | 'mild' | 'medium' | 'hot' | 'extra_hot';

/** Mirrors the `recipe_station` enum definition. Admin-editable server-side. */
export type Station =
  | 'grill' | 'fry' | 'cold' | 'bar' | 'bakery'
  | 'tandoor' | 'saute' | 'dessert' | 'other';

/** Presentational label for a station, used on the KDS tabs and badges. */
export const STATION_LABELS: Record<Station, string> = {
  grill: 'Grill',
  fry: 'Fry',
  cold: 'Cold / Salad',
  bar: 'Bar',
  bakery: 'Bakery',
  tandoor: 'Tandoor',
  saute: 'Sauté',
  dessert: 'Dessert',
  other: 'Other'
};

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  preparing: 'Preparing',
  ready: 'Ready',
  served: 'Served',
  cancelled: 'Cancelled',
  completed: 'Completed'
};

export const PREP_STATUS_LABELS: Record<PrepStatus, string> = {
  pending: 'To Start',
  preparing: 'Cooking',
  ready: 'Ready',
  voided: 'Voided'
};

export const TABLE_STATUS_LABELS: Record<TableStatus, string> = {
  available: 'Available',
  occupied: 'Occupied',
  reserved: 'Reserved',
  cleaning: 'Cleaning',
  maintenance: 'Maintenance'
};

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: 'Cash',
  card: 'Card',
  upi: 'UPI',
  wallet: 'Wallet',
  split: 'Split'
};

/**
 * Parse a money string to a number for display-side arithmetic only.
 * Returns 0 rather than NaN so a malformed value degrades to a visible 0
 * instead of rendering "NaN" into a total the cashier reads out.
 */
export function toAmount(value: string | number | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// ============================================================
//  Tables / zones
// ============================================================

export interface ITableZone {
  id?: number;
  name?: string;
  display_name?: string;
  description?: string;
  display_order?: number;
  is_active?: boolean;
  recipe_count?: number;
  table_count?: number;
}

export interface ITable {
  id?: number;
  table_number?: string;
  table_name?: string;
  capacity?: number;
  status?: TableStatus;
  zone_id?: number | null;
  zone_name?: string | null;
  position_x?: number | null;
  position_y?: number | null;
  shape?: string | null;
  is_combinable?: boolean;
  is_active?: boolean;
}

/** A table plus the order already running on it, as returned by the floor view. */
export interface IFloorTable extends ITable {
  active_order?: IActiveOrderBrief | null;
}

export interface IFloorZone {
  zone_id: number | null;
  zone_name: string;
  zone_display_name: string;
  display_order?: number;
  tables: IFloorTable[];
}

export interface IFloorView {
  zones: IFloorZone[];
  status_counts: Record<TableStatus, number>;
  total_tables: number;
}

export interface IActiveOrderBrief {
  id: number;
  order_number: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  total_amount: string;
  paid_amount: string;
  ordered_at: string | null;
  item_count: number;
}

// ============================================================
//  Customers
// ============================================================

export type CustomerTier = 'REGULAR' | 'SILVER' | 'GOLD' | 'PLATINUM';

export interface ICustomer {
  id?: number;
  customer_code?: string;
  name?: string;
  phone?: string;
  email?: string | null;
  address?: string | null;
  loyalty_points?: number;
  total_visits?: number;
  total_spent?: string;
  last_visit_at?: string | null;
  dietary_notes?: string | null;
  is_vip?: boolean;
  is_active?: boolean;
  tier?: CustomerTier;
}

// ============================================================
//  Recipes / menu
// ============================================================

export interface IRecipeCategory {
  id?: number;
  name?: string;
  display_name?: string;
  description?: string;
  display_order?: number;
  is_active?: boolean;
  recipe_count?: number;
  available_recipe_count?: number;
}

export interface IRecipeIngredient {
  id?: number;
  inventory_id?: number;
  inventory_name?: string | null;
  inventory_unit?: string | null;
  quantity?: string;
  unit?: string;
  is_optional?: boolean;
  is_prepped?: boolean;
  line_cost?: string;
  unit_cost?: string | null;
  in_stock?: boolean;
}

export interface IRecipe {
  id?: number;
  recipe_code?: string;
  name?: string;
  display_name?: string;
  category_id?: number | null;
  category_name?: string | null;
  category_display_name?: string | null;
  description?: string | null;
  instructions?: string | null;
  image_url?: string | null;
  selling_price?: string;
  cost_price?: string;
  margin_percent?: string;
  station?: Station;
  prep_time_minutes?: number;
  cook_time_minutes?: number;
  total_time_minutes?: number;
  is_vegetarian?: boolean;
  is_vegan?: boolean;
  is_spicy?: boolean;
  default_spice_level?: SpiceLevel | null;
  is_recommended?: boolean;
  is_available?: boolean;
  display_order?: number;
  is_active?: boolean;
  is_profitable?: boolean;
  can_be_ordered?: boolean;
  /** Only on the single-recipe fetch. */
  ingredients?: IRecipeIngredient[];
  ingredient_count?: number;
  /** Portions current stock supports; null when there are no ingredient lines. */
  portions_available?: number | null;
}

export interface IMenuSection {
  category_id: number | null;
  category_name: string;
  category_display_name: string;
  display_order?: number;
  recipes: IRecipe[];
}

export interface IMenu {
  sections: IMenuSection[];
  recipe_count: number;
  section_count: number;
}

export interface IStockCheck {
  recipe_id: number;
  is_makeable: boolean;
  portions_available: number | null;
  short_items: {
    inventory_id: number;
    inventory_name: string;
    required: string;
    available: string;
    unit: string;
  }[];
}

// ============================================================
//  Orders
// ============================================================

export interface IOrderItem {
  id?: number;
  item_type?: 'recipe' | 'inventory';
  item_id?: number;
  item_name?: string;
  quantity?: string;
  unit_price?: string;
  total_price?: string;
  modifiers?: Record<string, unknown> | null;
  cooking_instructions?: string | null;
  spice_level?: SpiceLevel | null;
  prep_status?: PrepStatus;
  station?: Station | null;
  recipe_id?: number | null;
  inventory_item_id?: number | null;
}

export interface IPayment {
  id?: number;
  amount?: string;
  payment_method?: PaymentMethod;
  payment_status?: PaymentStatus;
  split_group_id?: string | null;
  split_payer_name?: string | null;
  transaction_ref?: string | null;
  paid_at?: string | null;
  remarks?: string | null;
}

export interface IOrderSummary {
  id: number;
  order_number: string;
  reference_type: 'table' | 'customer' | 'walkin';
  reference_id: number;
  reference_label: string;
  table_id?: number | null;
  customer_id?: number | null;
  status: OrderStatus;
  order_type: OrderType;
  subtotal: string;
  tax_amount: string;
  discount_amount: string;
  total_amount: string;
  payment_status: PaymentStatus;
  paid_amount: string;
  due_amount: string;
  item_count: number;
  notes?: string | null;
  kitchen_notes?: string | null;
  ordered_at?: string | null;
  completed_at?: string | null;
}

export interface IOrderDetail extends IOrderSummary {
  items: IOrderItem[];
  payments: IPayment[];
  table?: {
    id: number;
    table_number: string;
    table_name?: string | null;
    zone_name?: string | null;
  } | null;
  customer?: {
    id: number;
    customer_code: string;
    name: string;
    phone?: string;
    loyalty_points?: number;
    tier?: CustomerTier;
  } | null;
}

// ============================================================
//  KDS
// ============================================================

export interface IKdsItem {
  id: number;
  order_id: number;
  item_name: string;
  quantity: string;
  station?: Station | null;
  prep_status: PrepStatus;
  modifiers?: Record<string, unknown> | null;
  cooking_instructions?: string | null;
  spice_level?: SpiceLevel | null;
  prep_started_at?: string | null;
  prep_completed_at?: string | null;
  minutes_in_prep?: number | null;
  /** Minutes since the ORDER was placed. The number a chef reacts to. */
  minutes_since_ordered?: number | null;
}

export interface IKdsTicket {
  order_id: number;
  order_number: string;
  reference_label: string;
  table_id?: number | null;
  table_number?: string | null;
  order_type: OrderType;
  order_status: OrderStatus;
  ordered_at?: string | null;
  max_wait_minutes: number;
  kitchen_notes?: string | null;
  item_count: number;
  items: IKdsItem[];
}

export interface IKdsBoard {
  station: string | null;
  tickets: IKdsTicket[];
  ticket_count: number;
  summary: { pending: number; preparing: number; ready: number };
  server_time: string;
}

export interface IKdsStationSummary {
  station: Station | null;
  pending: number;
  preparing: number;
  total: number;
}

// ============================================================
//  POS
// ============================================================

export interface IPosSummary {
  tables: { total: number } & Record<TableStatus, number>;
  open_orders: number;
  generated_at: string;
  today?: {
    completed_orders: number;
    revenue: string;
    average_ticket: string;
  };
}

export interface IBill {
  order_id: number;
  order_number: string;
  order_status: OrderStatus;
  order_type: OrderType;
  reference_label: string;
  ordered_at?: string | null;
  completed_at?: string | null;
  table?: { id: number; table_number: string; zone_name?: string | null } | null;
  customer?: {
    id: number; customer_code: string; name: string;
    phone?: string; loyalty_points?: number; tier?: CustomerTier;
  } | null;
  items: IOrderItem[];
  totals: {
    item_subtotal: string;
    tax_amount: string;
    discount_amount: string;
    total_amount: string;
    paid_amount: string;
    due_amount: string;
  };
  payments: IPayment[];
  payment_count: number;
  is_fully_paid: boolean;
  is_closable: boolean;
  /** Lines the kitchen has not plated. Blocks closing a takeaway early. */
  kitchen_outstanding: number;
  generated_at: string;
  tax_breakup?: {
    taxable_amount: string;
    tax_amount: string;
    total_with_tax: string;
    effective_rate_percent: string;
  };
}

// ============================================================
//  Reports
// ============================================================

/** Presets accepted by every report endpoint, plus an explicit window. */
export type ReportRange =
  | 'today' | 'yesterday' | 'last_7_days' | 'last_30_days'
  | 'this_month' | 'last_month' | 'custom';

/**
 * Runtime list for the range dropdown.
 *
 * `last_7_days` / `last_30_days` INCLUDE today, so they are 7 and 30 trading
 * days rather than 6 and 29 -- the backend resolves them that way and the label
 * here says so, because "last 7 days" meaning 6 is the kind of thing an owner
 * notices in a report.
 */
export const REPORT_PRESETS: { key: ReportRange; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'last_7_days', label: 'Last 7 days (incl. today)' },
  { key: 'last_30_days', label: 'Last 30 days (incl. today)' },
  { key: 'this_month', label: 'This month' },
  { key: 'last_month', label: 'Last month' },
  { key: 'custom', label: 'Custom range' }
];

export interface IReportRangeMeta {
  preset: ReportRange;
  from_date: string;
  to_date: string;
  day_count: number;
  timezone: string;
  utc_start: string;
  utc_end_exclusive: string;
}

export interface ISalesSummary {
  range: IReportRangeMeta;
  totals: {
    order_count: number;
    revenue: string;
    tax_amount: string;
    discount_amount: string;
    collected: string;
    outstanding: string;
    average_ticket: string;
  };
  by_payment_method?: {
    payment_method: PaymentMethod;
    payment_count: number;
    amount: string;
    share_percent: string;
  }[];
  by_order_type?: { order_type: OrderType; order_count: number; revenue: string }[];
  /** Trading-timezone hour buckets, keyed by local date. */
  hourly?: Record<string, {
    hour: number;
    label: string;
    order_count: number;
    revenue: string;
  }[]>;
}

export interface IItemSalesRow {
  item_type: 'recipe' | 'inventory';
  item_id: number;
  item_name: string;
  /** Joined from the recipe; null once the recipe or its category is gone. */
  category_display_name?: string | null;
  station: Station | null;
  quantity_sold: string;
  revenue: string;
  order_count: number;
  /** Average quantity per order — how many a typical table gets. */
  quantity_per_order: string;
  /** Only present when include_dead_stock brought the row in. */
  is_dead_stock?: boolean;
}

export interface IItemSales {
  range: IReportRangeMeta;
  sort_by: 'quantity' | 'revenue';
  /**
   * Not IRecipe: this report aggregates the denormalised `item_name` off the
   * order lines (so a row survives the recipe being renamed or retired) and
   * adds aggregate columns IRecipe has no field for. Reusing IRecipe here and
   * casting to `any` in the template would push that mismatch into the view.
   */
  items: IItemSalesRow[];
  distinct_items_sold: number;
  total_quantity: string;
  total_revenue: string;
  returned: number;
  truncated: boolean;
}

export interface IDailyTrend {
  range: IReportRangeMeta;
  series: {
    date: string;
    order_count: number;
    revenue: string;
    average_ticket: string;
  }[];
  day_count: number;
  trading_days: number;
  total_revenue: string;
  best_day: { date: string; order_count: number; revenue: string } | null;
  average_daily_revenue: string;
}

export interface IVoidReport {
  range: IReportRangeMeta;
  entries: {
    voided_by: number | null;
    voided_by_name: string;
    void_reason: string;
    item_name: string;
    line_count: number;
    order_count: number;
    quantity: string;
    value: string;
  }[];
  total_void_value: string;
  total_void_lines: number;
  cancelled_orders: number;
  cancelled_value: string;
  combined_loss: string;
  by_staff?: {
    voided_by: number | null;
    voided_by_name: string;
    line_count: number;
    order_count: number;
    total_value: string;
  }[];
}

export interface IKitchenReport {
  range: IReportRangeMeta;
  data_quality_warning?: string | null;
  overall: { lines_completed: number; avg_minutes: number; total_minutes: number };
  by_station: { station: Station | null; lines_completed: number; avg_minutes: number }[];
  slowest_item?: {
    item_name: string;
    station?: Station | null;
    lines_completed: number;
    quantity: string;
    avg_minutes: number;
    max_minutes: number | null;
  } | null;
  by_item?: {
    item_name: string;
    station?: Station | null;
    lines_completed: number;
    quantity: string;
    avg_minutes: number;
    max_minutes: number | null;
  }[];
  /** Queued seconds are wall-clock wait, which INCLUDES queue time. */
  note: string;
}

export interface ICustomerReport {
  range: IReportRangeMeta;
  totals: {
    total_customers: number;
    vip_customers: number;
    loyalty_points_outstanding: number;
    lifetime_spend: string;
    total_visits: number;
    avg_lifetime_value: string;
    avg_spend_per_visit: string;
  };
  new_customers_in_period: number;
  period_active_customers: number;
  top_customers: {
    customer_id: number;
    customer_code: string;
    name: string;
    phone?: string;
    is_vip: boolean;
    loyalty_points: number;
    total_visits: number;
    lifetime_spend: string;
    tier: CustomerTier;
    period_order_count: number;
    period_spend: string;
  }[];
  returned: number;
}