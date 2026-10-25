import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { ICurrencyOption, ITimezoneOption } from '../models/platform.model';

/**
 * Reference data the tenant screens pick from: the ISO 4217 currencies the
 * `currencies` table holds, and the IANA zones Python's `zoneinfo` can resolve.
 *
 * These deliberately live on `/api/super-admin`, not on the shared
 * `/api/v1/common` lookups the tenant app uses. The two APIs authenticate
 * differently and neither token works on the other's side: a platform token
 * carries no tenant `user_id`, so `auth_middleware.authenticate` (which
 * `requires_module` runs) refuses it outright. Served through the platform
 * guard instead, they are readable from the console and still come from the
 * same `CommonService` rows as everything else.
 */
@Injectable({ providedIn: 'root' })
export class PlatformLookupService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = `${this.config.get<string>('BASE_URL')}/api/super-admin`;
  }

  currencies(): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/lookups/currencies`);
  }

  timezones(): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/lookups/timezones`);
  }
}
