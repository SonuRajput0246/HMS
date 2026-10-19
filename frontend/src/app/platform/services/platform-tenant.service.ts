import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { ICreateTenant, IUpdateTenant } from '../models/platform.model';

export interface ITenantListQuery {
  page_size: number;
  page_number: number;
  search_value?: string;
  status?: string;
}

/**
 * Hotel lifecycle, as seen by the platform operator.
 *
 * Every call lands on `/api/v1/platform/tenants`, attributed to the platform
 * token alone -- these endpoints deliberately resolve no hotel, so no `X-Tenant`
 * header is sent for them.
 */
@Injectable({ providedIn: 'root' })
export class PlatformTenantService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = `${this.config.get<string>('BASE_URL')}/api/v1/platform`;
  }

  summary(): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/dashboard/summary`);
  }

  list(query: ITenantListQuery): Observable<IEntityResponse> {
    let params = new HttpParams()
      .set('page_size', query.page_size)
      .set('page_number', query.page_number);

    if (query.search_value) {
      params = params.set('search_value', query.search_value);
    }
    if (query.status) {
      params = params.set('status', query.status);
    }

    return this.http.get<IEntityResponse>(`${this.baseURL}/tenants`, { params });
  }

  get(id: number): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/tenants/${id}`);
  }

  create(payload: ICreateTenant): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/tenants`, payload);
  }

  update(id: number, payload: IUpdateTenant): Observable<IEntityResponse> {
    return this.http.patch<IEntityResponse>(`${this.baseURL}/tenants/${id}`, payload);
  }

  setStatus(id: number, isActive: boolean): Observable<IEntityResponse> {
    return this.http.patch<IEntityResponse>(`${this.baseURL}/tenants/${id}/status`, {
      is_active: isActive,
    });
  }

  archive(id: number): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/tenants/${id}/archive`, {});
  }

  restore(id: number): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/tenants/${id}/restore`, {});
  }

  /**
   * Set a new password on a hotel's own super admin, ending their sessions.
   *
   * The one recovery a hotel cannot perform itself: when its only admin loses
   * the password there is nobody inside the hotel who could reset it. The
   * server revokes that admin's live tokens, so this is not cosmetic.
   */
  resetAdminPassword(id: number, newPassword: string): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/tenants/${id}/reset-admin-password`, {
      password: newPassword,
    });
  }
}
