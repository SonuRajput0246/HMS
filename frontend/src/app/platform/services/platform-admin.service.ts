import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { ICreateSuperAdmin, IUpdateSuperAdmin } from '../models/platform.model';

export interface IAdminListQuery {
  page_size: number;
  page_number: number;
  search_value?: string;
  status?: string;
}

/**
 * The platform's own operators, as seen by an operator.
 *
 * Every call lands on `/api/v1/platform/admins`, attributed to the platform
 * token alone. Self-protection (you cannot deactivate or reset yourself) is
 * enforced server-side; the UI mirrors it by disabling those actions on your
 * own row, but the server is the authority.
 */
@Injectable({ providedIn: 'root' })
export class PlatformAdminService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = `${this.config.get<string>('BASE_URL')}/api/v1/platform`;
  }

  list(query: IAdminListQuery): Observable<IEntityResponse> {
    let params = new HttpParams()
      .set('page_size', query.page_size)
      .set('page_number', query.page_number);

    if (query.search_value) {
      params = params.set('search_value', query.search_value);
    }
    if (query.status) {
      params = params.set('status', query.status);
    }

    return this.http.get<IEntityResponse>(`${this.baseURL}/admins`, { params });
  }

  create(payload: ICreateSuperAdmin): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/admins`, payload);
  }

  get(id: number): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/admins/${id}`);
  }

  update(id: number, payload: IUpdateSuperAdmin): Observable<IEntityResponse> {
    return this.http.patch<IEntityResponse>(`${this.baseURL}/admins/${id}`, payload);
  }

  setStatus(id: number, isActive: boolean): Observable<IEntityResponse> {
    return this.http.patch<IEntityResponse>(`${this.baseURL}/admins/${id}/status`, {
      is_active: isActive,
    });
  }

  resetPassword(id: number, newPassword: string): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/admins/${id}/reset-password`, {
      new_password: newPassword,
    });
  }

  /**
   * Clear another administrator's authenticator (recovery).
   *
   * MFA is compulsory, so this is the only way back in for an operator who
   * lost their device -- a password reset alone leaves them still asked for a
   * code they cannot produce. The target's sessions are revoked server-side,
   * and they enrol again at their next sign-in.
   */
  resetMfa(id: number): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/admins/${id}/reset-mfa`, {});
  }
}
