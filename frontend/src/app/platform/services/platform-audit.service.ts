import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';

export interface IAuditLogQuery {
  page_size: number;
  page_number: number;
  action?: string;
  entity_type?: string;
  entity_id?: number;
  super_admin_id?: number;
  date_from?: string;
  date_to?: string;
}

/**
 * The platform audit trail.
 *
 * `GET /api/super-admin/audit-logs` is the reader for the rows every
 * management action already writes. It runs under the platform guard, like the
 * rest of this API, so no tenant slug travels with it.
 */
@Injectable({ providedIn: 'root' })
export class PlatformAuditService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = `${this.config.get<string>('BASE_URL')}/api/super-admin`;
  }

  list(query: IAuditLogQuery): Observable<IEntityResponse> {
    let params = new HttpParams()
      .set('page_size', query.page_size)
      .set('page_number', query.page_number);

    if (query.action) {
      params = params.set('action', query.action);
    }
    if (query.entity_type) {
      params = params.set('entity_type', query.entity_type);
    }
    if (query.entity_id != null) {
      params = params.set('entity_id', query.entity_id);
    }
    if (query.super_admin_id != null) {
      params = params.set('super_admin_id', query.super_admin_id);
    }
    if (query.date_from) {
      params = params.set('date_from', query.date_from);
    }
    if (query.date_to) {
      params = params.set('date_to', query.date_to);
    }

    return this.http.get<IEntityResponse>(`${this.baseURL}/audit-logs`, { params });
  }
}
