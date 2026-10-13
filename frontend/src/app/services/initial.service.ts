import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AppConfig } from '../core/config/config';

interface InstanceConfigResponse {
  status: boolean;
  message: string;
  data?: {
    instance_type?: string;
  };
}

export interface AppConfigResult {
  /** Where the instance type actually came from. */
  instanceTypeSource: 'backend' | 'config-json' | 'default';
  /** Set when the backend answered but disagreed with config.json. */
  mismatch?: { configJson: string; backend: string };
}

@Injectable({
  providedIn: 'root'
})
export class InitialService {

  private http = inject(HttpClient);
  private appConfig = inject(AppConfig);

  /** Holds API base URL loaded at app startup */
  baseUrl!: string;

  /**
   * Load runtime config in two steps.
   *
   * 1. `assets/config.json` supplies the API base URL. It is a static file, so
   *    it is the only thing available before the backend is contacted.
   * 2. The backend is then asked which instance it actually runs. That answer
   *    wins, because the backend is the thing that decides which endpoints
   *    exist.
   *
   * The previous design read `instance_type` from config.json alone, which
   * meant two files had to agree with no mechanism to notice when they did not.
   * A mismatch was silent: the frontend served /hms URLs against a CMS backend
   * and every one of them 404'd.
   */
  async loadAppConfig(): Promise<void> {
    await this.loadStaticConfig();

    const result = await this.resolveInstanceType();

    // Backend wins on a mismatch -- result.mismatch carries both values.
    // Otherwise fall back to what config.json declared.
    const resolved = result.mismatch
      ? result.mismatch.backend
      : this.normalisedInstanceType(
          this.appConfig.getOr('CONFIG_JSON_INSTANCE_TYPE', 'HMS')
        );

    this.appConfig.set('INSTANCE_TYPE', resolved);

    if (result.mismatch) {
      console.warn(
        `[instance] config.json says ${result.mismatch.configJson} but the ` +
        `backend reports ${result.mismatch.backend}. Using the backend value: ` +
        `it is the one that decides which endpoints exist. Fix ` +
        `instance_type in assets/config.json to stop this warning.`
      );
    }
  }

  private normalisedInstanceType(value: unknown): string {
    return String(value ?? '').trim().toUpperCase() === 'CMS' ? 'CMS' : 'HMS';
  }

  /**
   * Step 1: static config.
   *
   * Rejects when api_base_url is missing, because without it there is nothing
   * to call -- not even step 2. `instance_type` is optional here and defaults
   * are applied later.
   */
  private loadStaticConfig(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.http.get<any>('assets/config.json').subscribe({
        next: (data) => {
          const baseUrl = data?.global_setting?.api_base_url;

          if (!baseUrl) {
            reject('api_base_url missing in config.json');
            return;
          }

          this.appConfig.set('BASE_URL', baseUrl);

          // Kept only so a mismatch can be reported. InstanceService must NOT
          // read this -- it reads the resolved value, which may come from the
          // backend.
          const instanceType = data?.global_setting?.instance_type;
          if (instanceType) {
            this.appConfig.set('CONFIG_JSON_INSTANCE_TYPE', instanceType);
          }

          resolve();
        },
        error: reject
      });
    });
  }

  /**
   * Step 2: ask the backend which instance it is.
   *
   * Never rejects. A backend that is down, slow, or unreachable must not stop
   * the frontend booting -- offline development against a static config is a
   * legitimate setup, and a hard failure here would turn "backend is down"
   * into "the login page will not render at all", which hides the real
   * problem behind a confusing one.
   */
  private async resolveInstanceType(): Promise<AppConfigResult> {
    const fromConfig = this.normalisedInstanceType(
      this.appConfig.getOr('CONFIG_JSON_INSTANCE_TYPE', 'HMS')
    );

    try {
      const response = await firstValueFrom(
        this.http.get<InstanceConfigResponse>(
          `${this.appConfig.get('BASE_URL')}/api/v1/common/instance-config`
        )
      );

      const fromBackend = response?.data?.instance_type;

      if (!fromBackend) {
        return { instanceTypeSource: 'config-json' };
      }

      const normalised = this.normalisedInstanceType(fromBackend);

      if (normalised !== fromConfig) {
        return {
          instanceTypeSource: 'backend',
          mismatch: { configJson: fromConfig, backend: normalised }
        };
      }

      return { instanceTypeSource: 'backend' };
    } catch (error: any) {
      console.warn(
        `[instance] Could not reach ${this.appConfig.get('BASE_URL')} to confirm ` +
        `the instance type (${error?.message ?? error}). Falling back to ` +
        `instance_type from config.json.`
      );
      return { instanceTypeSource: 'config-json' };
    }
  }
}