import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { IPlatformLoginData, IPlatformProfile } from '../models/platform.model';

/**
 * Platform (super admin) session, kept apart from the tenant session.
 *
 * Both can be open in the same browser, so they cannot share storage keys: a
 * tenant token under the platform's key (or the reverse) would be sent to the
 * wrong API and rejected, or -- worse -- accepted by a scope check that only
 * looked at whether a token was present. `hms_sa_*` is the platform namespace.
 *
 * Requests to `/api/super-admin` carry no `X-Tenant-Slug`: the interceptor
 * skips it for this API, because a platform caller has no workspace.
 */
@Injectable({ providedIn: 'root' })
export class PlatformAuthService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  login(payload: { email: string; password: string }): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/super-admin/auth/login`,
      payload
    );
  }

  me(): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/api/super-admin/auth/me`);
  }

  /**
   * Second step of sign-in. Public like `login`: it carries the short-lived
   * `temp_token` from the first step, not a session. One endpoint finishes
   * both shapes of that step -- proving the code for an enrolled account, or
   * confirming the enrolment and then signing in -- because they are the same
   * question ("does a correct code from this account's authenticator exist?")
   * and splitting them would only let a client skip the second.
   */
  verifyMfa(payload: { temp_token: string; totp: string }): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/super-admin/auth/verify-mfa`,
      payload
    );
  }

  /** Begin (re)enrolment: returns the otpauth URI and secret. MFA stays off
   * until `enableMfa` confirms a code, so an abandoned attempt simply makes
   * the next sign-in run the compulsory setup step again. */
  setupMfa(): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/super-admin/auth/mfa/setup`, {});
  }

  enableMfa(payload: { totp: string }): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/super-admin/auth/mfa/enable`,
      payload
    );
  }

  /**
   * Self-service password change. No id is sent: the server reads the admin
   * from the token, so this can only ever change the caller's own password.
   */
  changePassword(payload: {
    current_password: string;
    new_password: string;
  }): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/super-admin/auth/change-password`,
      payload
    );
  }

  logout(): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/super-admin/auth/logout`,
      {}
    );
  }

  saveSession(data: IPlatformLoginData): void {
    sessionStorage.setItem('hms_sa_accessToken', data.access_token);
    localStorage.setItem('hms_sa_profile', JSON.stringify(data.profile));
  }

  /**
   * Refresh just the cached profile. Used after a security change that alters
   * a profile field (enabling MFA) so the stored copy does not drift from the
   * server; the token is untouched.
   */
  saveProfile(profile: IPlatformProfile): void {
    localStorage.setItem('hms_sa_profile', JSON.stringify(profile));
  }

  get profile(): IPlatformProfile | null {
    const raw = localStorage.getItem('hms_sa_profile');
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as IPlatformProfile;
    } catch {
      return null;
    }
  }

  get fullName(): string {
    const profile = this.profile;
    return profile ? `${profile.first_name} ${profile.last_name}`.trim() : '';
  }

  clearSession(): void {
    sessionStorage.removeItem('hms_sa_accessToken');
    localStorage.removeItem('hms_sa_profile');
  }
}
