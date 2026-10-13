import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';

/**
 * Kitchen Display System.
 *
 * Read-heavy and latency sensitive -- these are the calls a kitchen screen
 * re-polls, so nothing here is cached and nothing debounces server state.
 */
@Injectable({ providedIn: 'root' })
export class CmsKdsService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  /**
   * The kitchen queue.
   *
   * order_by defaults to oldest_first, which the server treats as
   * overdue-first -- the ticket that has waited longest leads the board.
   * include_ready pulls plated lines back in for a drill-down view.
   */
  getTickets(data: {
    station?: string | null;
    order_by?: 'oldest_first' | 'newest_first';
    include_ready?: boolean;
  }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/kds/get-tickets`, {
      station: data.station ?? null,
      order_by: data.order_by ?? 'oldest_first',
      include_ready: data.include_ready ?? false
    });
  }

  /** One ticket in full, for the drill-down. */
  getTicket(orderId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/kds/get-ticket/${orderId}`);
  }

  /** Per-station outstanding counts, for the station tab badges. */
  getStationSummary(): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/kds/get-station-summary`);
  }

  /**
   * Move one line through the kitchen.
   *
   * 'ready' is allowed straight from 'pending': most KDS screens are one tap,
   * and forcing a tap-to-start first doubles the taps for every dish.
   * Moving back to 'pending' requeues the line and restarts its timer.
   */
  updatePrepStatus(orderId: number, orderItemId: number, prepStatus: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/kds/${orderId}/prep-status`, {
      order_item_id: orderItemId, prep_status: prepStatus
    });
  }

  /**
   * Mark every still-cooking line on a ticket ready.
   *
   * Pass `station` to bump only that pass -- a table's grill items and its
   * cocktails go out at different times.
   */
  bumpOrder(orderId: number, station?: string | null): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/kds/bump`, {
      order_id: orderId, station: station ?? null
    });
  }
}