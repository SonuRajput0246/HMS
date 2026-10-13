import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';

/**
 * Table zones, tables, and the combined floor view.
 *
 * Customer methods used to live here too, on the grounds that customers and
 * tables "share the till". That holds at the POS and nowhere else -- the
 * customer management screen injected a service named after the floor purely to
 * reach /api/v1/customer. They now live in CmsCustomerService; the POS screen
 * injects both.
 */
@Injectable({ providedIn: 'root' })
export class CmsFloorService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  // ---- zones ----------------------------------------------------------

  getZones(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/table-zone/get`, data);
  }

  upsertZone(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/table-zone/upsert`, data);
  }

  getZoneTableCount(zoneId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/table-zone/get-table-count?id=${zoneId}`);
  }

  // ---- tables ---------------------------------------------------------

  getTables(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/table/get`, data);
  }

  getTableById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/table/get-by-id?id=${id}`);
  }

  /** Whole floor grouped by zone with any live order per table. One call. */
  getFloorView(): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/table/get-floor-view`);
  }

  upsertTable(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/table/upsert`, data);
  }

  /**
   * Manual status flip.
   *
   * The backend refuses to release a table that still has an open order, so a
   * 409 here means "settle the order first" -- the caller should show that
   * message rather than silently retrying.
   */
  updateTableStatus(id: number, status: string, remarks?: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/table/update-status`, {
      id, status, remarks: remarks ?? null
    });
  }
}