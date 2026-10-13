import { HttpClient } from '@angular/common/http';
import { EventEmitter, inject, Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { IEntityResponse } from '../models/ICommon.model';
import { AppConfig } from '../core/config/config';
import { STORAGE_KEYS } from '../core/config/storage-keys';

@Injectable({
  providedIn: 'root'
})
export class CommonService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;
  private mfaEnabledSignal = signal<boolean>(this.getInitialMfaStatus());

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  routeChange: EventEmitter<boolean> = new EventEmitter<boolean>();

  getUserFullName(): string {
    const userData = localStorage.getItem(STORAGE_KEYS.USER_DATA);
    if (!userData) {
      return '';
    }
    const user = JSON.parse(userData);
    const firstName = user.first_name || '';
    const lastName = user.last_name || '';
    return `${firstName} ${lastName}`.trim();
  }


  private getInitialMfaStatus(): boolean {
    const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.USER_DATA) || '{}');
    return !!user?.mfa_enabled;
  }

  getMFAEnabledSignal() {
    return this.mfaEnabledSignal.asReadonly();
  }

  setMFAEnabledStatus(status: boolean) {
    this.mfaEnabledSignal.set(status);
    const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.USER_DATA) || '{}');
    user.mfa_enabled = status;
    localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(user));
  }

  getLoggedInUserId(): number {
    const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.USER_DATA) || '{}');
    return user?.id || 0;
  }

  getMenuAccess(): any[] {
    const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.USER_DATA) || '{}');
    return user?.menu_access || [];
  }

  getLoginSliderData(): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/api/v1/common/get-login-slider-data`, {})
  }

  getCountriesList(data: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/common/get-all-countries`, data)
  }

  getStatesList(data: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/common/get-all-states`, data)
  }

  getCitiesList(data: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/common/get-all-cities`, data)
  }

  getCurrenciesList(data: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/common/get-all-currencies`, data)
  }

  /**
   * Options for one enum definition held in the `enum_definitions` /
   * `enum_options` tables, e.g. 'guests_id_type', 'gender', 'room_status'.
   * Dropdowns bind to this so an option added in the admin UI shows up here
   * without a frontend change.
   */
  getEnumOptions(enumKey: string): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/common/get-enum-options`, { enum_key: enumKey })
  }
}
