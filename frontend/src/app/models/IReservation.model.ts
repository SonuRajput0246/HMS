import { IGenericPagination } from "./ICommon.model";
export interface IReservations {
    reservation_id?: number;
    check_in_date?: string;
    check_out_date?: string;
    created_at?: string;
    room_id?: number;
    room_number?: string;
    /** `total_amount` and `total_nights` come back as strings from MySQL
     *  Numeric/Integer columns; left as-is because the grid formats them. */
    total_amount?: number | string;
    total_nights?: number | string;
    /**
     * Named `reservation_status`, NOT `status`.
     *
     * The list endpoint previously returned this under `status`, which collided
     * with the envelope's own `status: boolean` and read ambiguously in the
     * template. Renamed to match the detail endpoint's `reservation_status` and
     * the column name. Update any binding still using `.status`.
     */
    reservation_status?: string;
    created_by?: string | null;
    guests_added?: boolean;
}
export interface IFilterReservations extends IGenericPagination {
    from_date?: Date | string | null;
    to_date?: Date | string | null;
    search_room_number_value?: string;
    reservation_status?: string;
}
export interface IAvailableRooms {
    room_id?: number;
    room_number?: string;
    room_type?: string;
    price?: number;
    extra_bed_allowed: boolean;
    extra_bed_price: number;
    max_adults: number;
    max_children: number;
    amenities?: string[];
}
export interface IFilterAvailableRooms extends IGenericPagination {
    check_in?: Date | string | null;
    check_out?: Date | string | null;
    room_type_id?: number | null;
    /**
     * NEW — when re-checking availability while editing a reservation,
     * the backend must ignore this reservation's own booking so the
     * currently assigned room stays selectable.
     */
    exclude_reservation_id?: number | null;
    /**
     * NEW (optional) — free-text match on room number / type. The room
     * picker also filters client-side, so omitting it only limits the
     * search to the currently loaded page.
     */
    search_value?: string;
}
export interface IRoomType {
    id?: number;
    name?: string;
    description?: string;
    base_price?: number;
    extra_bed_allowed?: boolean;
    extra_bed_price?: number;
    max_adults?: number;
    max_children?: number;
}
// ============================================================================
//  UPDATE RESERVATION — frontend-defined contract
//  Mirrors docs/API-CONTRACT-reservation-update.md
// ============================================================================
/** PUT /api/v1/reservation/update */
export interface IUpdateReservationPayload {
    reservation_id: number;
    room_id: number;
    check_in_date: string;          // YYYY-MM-DD
    check_out_date: string;         // YYYY-MM-DD
    total_nights: number;
    total_amount: number;
    total_amount_override?: boolean;
    total_amount_override_reason?: string;
    updated_at?: string | null;     // optimistic concurrency token
}
/**
 * One row of the payment ledger (read-only history).
 * Mirrors the backend `payments` table — see the Flask `Payment` model.
 */
export interface IReservationPayment {
    id?: number;
    reservation_id?: number;
    folio_id?: number | null;
    payment_type?: string;          // advance | partial | full | refund
    amount?: number;
    currency?: string;
    /** server-computed: amount x exchange_rate */
    base_amount?: number;
    exchange_rate?: number;
    payment_method?: string;        // cash | card | upi | net_banking | online
    payment_status?: string;        // pending | success | failed | refunded
    transaction_ref?: string | null;
    remarks?: string | null;          // note the plural — the column is `remarks`
    paid_at?: string | null;          // ISO timestamp, nullable server-side
    verified_at?: string | null;
}
/** POST /api/v1/reservation/advance-payment-details */
export interface IInsertPaymentPayload extends IReservationPayment {
    reservation_id: number;
    payment_type: string;
    payment_method: string;
    amount: number;
    /**
     * NOT sent by the client. The backend derives it from the auth token —
     * a client must never be able to assert who verified a payment.
     */
    verified_by?: number;
}
export interface IDraftReservationData {
    reservation_id: number;
    // Step 1: Room Details
    room_id?: number;
    room_number?: string;
    room_type?: string;
    price_per_night?: number;
    total_amount?: number;
    check_in_date?: string;
    check_out_date?: string;
    total_nights?: number;
    // Step 2: Guest Details (Added later)
    guest_id?: number;
    guest_name?: string;
    guest_phone?: string;
    // Step 3: Payment Details (Added later)
    advance_amount?: number;
    payment_mode?: string;
}
