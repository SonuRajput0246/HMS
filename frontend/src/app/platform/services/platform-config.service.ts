import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { timer } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { PLATFORM_HOST_LABELS } from '../../core/platform-host';
import { IEntityResponse } from '../../models/ICommon.model';
import { IPlatformConfig } from '../models/platform.model';

/**
 * The deployment this console is running against.
 *
 * The panel has to print the host a tenant will really be served on, and that
 * is a property of the *deployment*, not of the page: `demo.localhost:4200` in
 * development, `demo.example.com` in production. It used to be hardcoded as
 * `localhost:4200` in three places, so the subdomain column, the slug suffix
 * and the create form's URL preview all began lying the moment the console was
 * served from a real host.
 *
 * The value now comes from the server -- `PUBLIC_BASE_URL` (or the backend's
 * `TENANT_BASE_DOMAIN`, which wins when set) handed over by
 * `GET /api/v1/platform/config` -- so one build serves every environment and
 * there is nothing to remember to change at release.
 *
 * TWO THINGS AN OPERATOR SHOULD KNOW
 * ----------------------------------
 *   * `PUBLIC_BASE_URL` is read once, when the backend starts. Editing `.env`
 *     does nothing until it is restarted -- this was measured, not assumed.
 *   * The browser reads it once per page load. A tab left open across a
 *     backend restart keeps the value it was opened with; reload it.
 *
 * AND ONE THING THIS CLASS DOES ABOUT IT
 * --------------------------------------
 * The fallback below keeps the surface working when the call cannot be made,
 * because a console with no tenant hosts is a worse console. But a *silent*
 * fallback is how a wrong host survives a whole session looking legitimate --
 * which is precisely the bug this class replaced. So the fallback is the
 * window's own domain recomputed on every read, a failed call is retried before
 * it is believed, and when it finally is believed it says so in the console.
 */
@Injectable({ providedIn: 'root' })
export class PlatformConfigService {

  /** Retries after the first attempt, spanning a backend restart. */
  private static readonly MAX_RETRIES = 3;
  private static readonly RETRY_DELAY_MS = 700;

  private _http = inject(HttpClient);
  private _appConfig = inject(AppConfig);

  /**
   * Set only by a successful call. `null` means the value below is an
   * assumption about this deployment, not a statement from it.
   */
  private fromDeployment: string | null = null;

  private retries = 0;

  constructor() {
    this.load();
  }

  /** What a slug is suffixed with: `localhost:4300`, `example.com`. */
  get tenantHostSuffix(): string {
    return this.fromDeployment ?? this.assumeFromWindow();
  }

  /** Where a given hotel is served: `demo.example.com`. */
  tenantHost(slug: string): string {
    return `${slug || 'subdomain'}.${this.tenantHostSuffix}`;
  }

  private load(): void {
    this._http
      .get<IEntityResponse>(`${this._appConfig.get<string>('BASE_URL')}/api/v1/platform/config`)
      .subscribe({
        next: (resp: IEntityResponse) => {
          const suffix = (resp?.data as IPlatformConfig | null)?.tenant_host_suffix;
          if (suffix) {
            this.fromDeployment = suffix.toLowerCase();
          }
        },
        error: (err: HttpErrorResponse) => this.retryOrReport(err),
      });
  }

  /**
   * A backend that is restarting refuses the connection outright (`status: 0`)
   * or is briefly unable to answer (5xx). Both are moments, not verdicts: a
   * short retry turns them into a non-event instead of a session lived on a
   * guessed host.
   *
   * Anything else -- a 404 from a deployment too old to have the endpoint, a
   * 401 -- is a verdict, and retrying it would only delay the warning.
   */
  private retryOrReport(err: HttpErrorResponse): void {
    const status = err?.status ?? 0;
    const worthRetrying = status === 0 || status >= 500;

    if (worthRetrying && this.retries < PlatformConfigService.MAX_RETRIES) {
      this.retries += 1;
      timer(PlatformConfigService.RETRY_DELAY_MS).subscribe(() => this.load());
      return;
    }

    // Deliberately loud. The fallback is usually right, and "usually" is
    // exactly why a wrong host can go unnoticed for a whole session.
    const url = `${this._appConfig.get<string>('BASE_URL')}/api/v1/platform/config`;
    console.warn(
      `[platform] ${url} could not be read (HTTP ${status || 'no response'}). ` +
        `Tenant hosts fall back to this window's own domain ` +
        `(${this.assumeFromWindow()}).`
    );
  }

  /**
   * What this deployment is assumed to look like when the server has not said.
   *
   * The console is always served from a label of its own -- `admin.localhost`,
   * `console.example.com` -- and a hotel's URL is that same host with `admin`
   * swapped for the hotel's slug. So the assumption is: drop the console's own
   * label, keep the rest.
   *
   * The test for "is this my own label" is the same constant the routing split
   * uses (`PLATFORM_HOST_LABELS`), so the host the console decided it is on and
   * the host it derives for hotels can never disagree. A count-based rule
   * ("three or more labels") was tried first and is wrong in both directions:
   * `admin.localhost` has two labels and does need one dropped, while
   * `demo.localhost` has two and must not.
   *
   * `tenant_management_service._tenant_host_suffix` is the authority and has the
   * final say, because in production it reads the configured
   * `TENANT_BASE_DOMAIN` rather than deriving anything. This is only the
   * fallback for when it could not be asked -- see the retry logic above.
   */
  private assumeFromWindow(): string {
    return PlatformConfigService.deriveSuffix(
      window.location.hostname,
      window.location.port
    );
  }

  /**
   * The same rule as a pure function -- see the spec that pins it, and
   * `platform-config.service.spec.ts` for the cases.
   */
  static deriveSuffix(hostname: string, port: string): string {
    const host = (hostname || '').toLowerCase().trim().replace(/:\d+$/, '');
    if (!host) {
      return port ? `:${port}` : '';
    }

    // An IP literal has no labels to spare: `5.6.7.8` minus its first would be
    // `6.7.8`, a host nobody could reach. Nor is an IPv6 address.
    const isIpLiteral = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host) || host.includes('[');

    const labels = host.split('.').filter(label => label.length > 0);
    const hasConsoleLabel =
      !isIpLiteral && labels.length >= 2 && PLATFORM_HOST_LABELS.includes(labels[0]);

    const suffix = hasConsoleLabel ? labels.slice(1).join('.') : host;

    return port ? `${suffix}:${port}` : suffix;
  }
}
