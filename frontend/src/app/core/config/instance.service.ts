import { Injectable, inject } from '@angular/core';
import { AppConfig } from './config';

/** The two products this codebase ships as. */
export type InstanceType = 'HMS' | 'CMS';

/**
 * Single source of truth for "which product am I?".
 *
 * The value is resolved by `InitialService` before the router ever activates,
 * from the BACKEND where possible (`GET /api/v1/common/instance-config`),
 * falling back to `instance_type` in `assets/config.json` when the backend
 * cannot be reached. The backend wins because it is what decides which
 * endpoints exist; the frontend asking its own static file what it is
 * supports was how the two could silently disagree.
 *
 * Ordering matters: every `getter` below is only correct once that initializer
 * has resolved, so nothing may read them at module scope.
 *
 * Every navigation out of shared code (auth flows, 404 page, redirects) should
 * go through `homeUrl` rather than spelling `/hms/...` out. Feature folders own
 * their own internal paths and can hardcode them -- they only load when their
 * instance is active.
 */
@Injectable({ providedIn: 'root' })
export class InstanceService {

  private appConfig = inject(AppConfig);

  /**
   * Normalises whatever is in config.json. An unrecognised or missing value
   * falls back to HMS rather than throwing: a blank instance_type should not
   * take the whole app down at bootstrap.
   */
  get type(): InstanceType {
    const raw = this.appConfig.getOr<string>('INSTANCE_TYPE', 'HMS');
    return String(raw ?? '').trim().toUpperCase() === 'CMS' ? 'CMS' : 'HMS';
  }

  get isHms(): boolean {
    return this.type === 'HMS';
  }

  get isCms(): boolean {
    return this.type === 'CMS';
  }

  /** URL segment for the active instance: `'hms'` or `'cms'`. */
  get prefix(): string {
    return this.type.toLowerCase();
  }

  /** Landing URL after login: `/hms/dashboard` or `/cms/dashboard`. */
  get homeUrl(): string {
    return `/${this.prefix}/dashboard`;
  }

  /** Human-readable product name, for chrome and welcome messages. */
  get label(): string {
    return this.type === 'CMS' ? 'CMS' : 'HMS';
  }
}