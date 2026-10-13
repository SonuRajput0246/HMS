import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AppConfig } from '../core/config/config';

/**
 * Loads the static runtime config before the app renders.
 *
 * `assets/config.json` is the only thing available before the backend is
 * contacted, so it is the only source. `api_base_url` is the one value that
 * cannot be defaulted: without it there is nothing to call, so boot fails
 * loudly rather than rendering a login page that silently never submits.
 *
 * `instance_type` is no longer read. There is one product, so the frontend and
 * the backend cannot disagree about which endpoints exist.
 */
@Injectable({
  providedIn: 'root'
})
export class InitialService {

  private http = inject(HttpClient);
  private appConfig = inject(AppConfig);

  /** Holds API base URL loaded at app startup */
  baseUrl!: string;

  async loadAppConfig(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.http.get<any>('assets/config.json').subscribe({
        next: (data) => {
          const baseUrl = data?.global_setting?.api_base_url;

          if (!baseUrl) {
            reject('api_base_url missing in config.json');
            return;
          }

          this.baseUrl = baseUrl;
          this.appConfig.set('BASE_URL', baseUrl);

          resolve();
        },
        error: reject
      });
    });
  }
}