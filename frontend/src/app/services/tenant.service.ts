import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AppConfig } from '../core/config/config';
import { InstanceService } from '../core/config/instance.service';
import { TenantState } from '../core/config/tenant';
import { IEntityResponse } from '../models/ICommon.model';

/**
 * The hotel's own branding, as the public `tenant-info` endpoint reports it.
 *
 * The names match the endpoint's JSON rather than any local convention, because
 * this is a wire shape. `display_name` is the hotel's `company_name` setting,
 * which is what its guests should see -- the registry `name` on the envelope
 * around it is the platform admin's label and is not shown to anyone else.
 */
export interface TenantBranding {
  display_name: string;
  app_logo_image: string;
  terms_condition_url: string;
  privacy_policy_url: string;
}

export interface TenantInfo {
  slug: string;
  name: string;
  branding: TenantBranding;
}

/**
 * Resolves the host's hotel once, during boot.
 *
 * Runs after `InitialService`, because it needs `BASE_URL`, and blocks the
 * first render for the same reason `config.json` does: the login page has to
 * know whose it is before a user types a password into it. It never rejects --
 * a failed boot would leave a blank screen, and "we could not ask" is not the
 * same as "this hotel does not exist", so those land in different states.
 */
@Injectable({
  providedIn: 'root'
})
export class TenantService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);
  private instance = inject(InstanceService);

  /**
   * What the host resolved to.
   *
   * Starts at `ok` so the app is usable if the guard is ever reached before
   * boot finishes; the two refusals are only set once an answer is in hand.
   */
  state: TenantState = 'ok';

  /** The resolved hotel's branding, or null when it was not reported. */
  branding: TenantBranding | null = null;

  async load(): Promise<void> {
    const slug = this.instance.slug;
    if (!slug) {
      /// The host names no hotel. The API refuses such a request too, so the app
      /// matches it rather than guessing a default.
      this.state = 'no-tenant';
      return;
    }

    const url = `${this.config.get('BASE_URL')}/api/v1/common/tenant-info`;

    return new Promise<void>((resolve) => {
      this.http.get<IEntityResponse>(url).subscribe({
        next: (res) => {
          const info = res?.data as TenantInfo | undefined;
          if (info) {
            this.branding = info.branding || null;
            this.applyBranding(info.branding);
          }
          this.state = 'ok';
          resolve();
        },
        error: (err) => {
          /// A 404 is the server stating that this hotel does not exist; any
          /// other failure is the server being unreachable, which says nothing
          /// about the hotel. Only the former is a refusal.
          this.state = err?.status === 404 ? 'unknown' : 'ok';
          resolve();
        },
      });
    });
  }

  /**
   * Publish the hotel's branding where the rest of the app reads config.
   *
   * `app_logo_image`, the two policy links and the hotel's name were static
   * keys in `config.json` in the single-tenant world. They are per-hotel now,
   * so they are published here instead; nothing may read them before boot ends.
   */
  private applyBranding(branding: TenantBranding | null | undefined): void {
    if (!branding) {
      return;
    }
    if (branding.display_name) {
      this.instance.label = branding.display_name;
    }
    this.config.set('COMPANY_NAME', branding.display_name);
    this.config.set('APP_LOGO_IMAGE', branding.app_logo_image);
    this.config.set('TERMS_CONDITION_URL', branding.terms_condition_url);
    this.config.set('PRIVACY_POLICY_URL', branding.privacy_policy_url);
  }
}
