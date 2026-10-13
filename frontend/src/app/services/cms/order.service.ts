import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { IBill, IOrderDetail, IPosSummary } from '../../models/ICms.model';

/**
 * Order lifecycle and the till read model.
 *
 * Ordering and payment live in the same service because they are one
 * transaction from the cashier's point of view: nothing about "create order"
 * is useful without the ability to settle it.
 */
@Injectable({ providedIn: 'root' })
export class CmsOrderService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  // ---- lifecycle ------------------------------------------------------

  /**
   * Open an order against a table, a customer, or as a walk-in.
   *
   * A 409 here means the table already has an open order and the response
   * carries `existing_order_id` -- the POS should open THAT order rather than
   * surfacing an error, because the guest is already seated.
   */
  createOrder(data: {
    reference_type: 'table' | 'customer' | 'walkin';
    reference_id?: number | null;
    order_type?: string;
    tax_amount?: string | number;
    discount_amount?: string | number;
    notes?: string | null;
    kitchen_notes?: string | null;
  }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/create`, data);
  }

  getOrders(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/get`, data);
  }

  getOrderById(orderId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/order/get-by-id/${orderId}`);
  }

  /** The live order on a table, for when a waiter taps an occupied table. */
  getActiveOrderByTable(tableId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/order/get-active-by-table/${tableId}`);
  }

  // ---- line items -----------------------------------------------------

  addItem(orderId: number, data: {
    recipe_id?: number;
    inventory_id?: number;
    quantity: string | number;
    unit_price?: string | number;
    modifiers?: Record<string, unknown>;
    cooking_instructions?: string | null;
    spice_level?: string | null;
  }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/items`, data);
  }

  updateItemQuantity(orderId: number, orderItemId: number, quantity: string | number): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/items/update-quantity`, {
      order_item_id: orderItemId, quantity
    });
  }

  /**
   * Void a line.
   *
   * `reason` is mandatory server-side: a void is money that was almost taken
   * and the loss report groups by reason, so the cashier is asked for it.
   */
  voidItem(orderId: number, orderItemId: number, reason: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/items/void`, {
      order_item_id: orderItemId, reason
    });
  }

  // ---- status / settlement -------------------------------------------

  updateStatus(orderId: number, status: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/status`, { status });
  }

  cancelOrder(orderId: number, reason: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/cancel`, { reason });
  }

  /**
   * Record one payment.
   *
   * A split bill is several calls sharing a split_group_id. The server rejects
   * an amount above the outstanding balance, so the caller should send the
   * exact remaining figure rather than raw cash tendered.
   */
  processPayment(orderId: number, data: {
    amount: string | number;
    payment_method: string;
    transaction_ref?: string | null;
    split_group_id?: string | null;
    split_payer_name?: string | null;
    remarks?: string | null;
  }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/payment`, data);
  }

  /**
   * Close a settled order, freeing the table.
   *
   * complete_payment=true takes the remaining balance first, which is the
   * usual "settle and close" path. Without it the order must already be paid
   * in full or the call 409s.
   */
  closeOrder(orderId: number, data: {
    complete_payment?: boolean;
    payment_method?: string;
    transaction_ref?: string | null;
  }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/order/${orderId}/close`, {
      complete_payment: data.complete_payment ?? false,
      payment_method: data.payment_method ?? null,
      transaction_ref: data.transaction_ref ?? null
    });
  }

  // ---- till read model ------------------------------------------------

  /** Receipt / bill. A read -- rendering it can never move money. */
  getBill(orderId: number): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/pos/get-bill`, { order_id: orderId });
  }

  /** Landing counters for the till. */
  getSummary(includeTodayRevenue = true): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/pos/get-summary`, {
      include_today_revenue: includeTodayRevenue
    });
  }
}