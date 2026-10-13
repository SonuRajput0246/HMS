import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';

/**
 * Customer records and loyalty points.
 *
 * These used to live in CmsFloorService, on the reasoning that customers and
 * tables "share the till". That reasoning holds at the POS and nowhere else:
 * the customer management screen injected a service named after the floor to
 * call /api/v1/customer, and never touched a single zone or table method.
 *
 * The POS screen now injects both services, which costs one extra line there
 * and buys an honest name everywhere else.
 */
@Injectable({ providedIn: 'root' })
export class CmsCustomerService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  getCustomers(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/customer/get`, data);
  }

  getCustomerById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/customer/get-by-id?id=${id}`);
  }

  lookupByPhone(phone: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/customer/lookup-by-phone`, { phone });
  }

  /**
   * Minimal walk-in capture (name + phone).
   *
   * Returns the EXISTING customer with status 200 when the phone is already
   * known, so a caller can treat both outcomes as "customer ready" and bill
   * the original record.
   */
  quickCreateCustomer(data: { name: string; phone: string }): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/customer/quick-create`, data);
  }

  upsertCustomer(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/customer/upsert`, data);
  }

  redeemPoints(id: number, points: number): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/customer/redeem-points`, { id, points });
  }
}