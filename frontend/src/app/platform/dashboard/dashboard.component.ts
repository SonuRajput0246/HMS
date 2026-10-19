import { Component, inject } from '@angular/core';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../models/ICommon.model';
import { ITenantSummary } from '../models/platform.model';
import { PlatformTenantService } from '../services/platform-tenant.service';

type SummaryKey = keyof ITenantSummary;

interface ISummaryCard {
  key: SummaryKey;
  label: string;
  icon: string;
  tone: string;
}

/** One band of the tenant-composition bar. `tone` names the CSS modifier. */
interface ICompositionBand {
  key: SummaryKey;
  label: string;
  tone: string;
}

/**
 * Platform-wide totals. The numbers span every tenant because the request has
 * none bound -- that is the point of the screen, not a filter that failed.
 */
@Component({
  selector: 'app-platform-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class PlatformDashboardComponent {

  private _tenants = inject(PlatformTenantService);
  private _snackbar = inject(CustomSnackbarService);

  isLoading = false;
  summary: ITenantSummary | null = null;

  readonly cards: ISummaryCard[] = [
    { key: 'total_tenants', label: 'Total hotels', icon: 'storefront', tone: 'neutral' },
    { key: 'active_tenants', label: 'Active', icon: 'check_circle', tone: 'positive' },
    { key: 'inactive_tenants', label: 'Inactive', icon: 'pause_circle', tone: 'warn' },
    { key: 'archived_tenants', label: 'Archived', icon: 'archive', tone: 'muted' },
    { key: 'total_users', label: 'Users', icon: 'group', tone: 'neutral' },
  ];

  /**
   * The three lifecycle bands that make up the total, in that order.
   *
   * Inactive and archived are counted separately by the backend because they are
   * different decisions: one hotel stopped trading and can be switched back, the
   * other has left the platform and its subdomain no longer resolves.
   */
  readonly composition: ICompositionBand[] = [
    { key: 'active_tenants', label: 'Active', tone: 'active' },
    { key: 'inactive_tenants', label: 'Inactive', tone: 'inactive' },
    { key: 'archived_tenants', label: 'Archived', tone: 'archived' },
  ];

  ngOnInit(): void {
    this.loadSummary();
  }

  loadSummary(): void {
    this.isLoading = true;
    this._tenants.summary()
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.summary = (resp?.data as ITenantSummary) ?? null;
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not load the summary.',
            'error'
          );
        },
      });
  }

  value(key: SummaryKey): number {
    return this.summary ? this.summary[key] : 0;
  }

  /**
   * A band's width as a percentage of the total, for the composition bar.
   * Returns 0 rather than NaN when nothing has been provisioned yet, so the
   * bar renders as an empty track instead of collapsing the layout.
   */
  share(key: SummaryKey): number {
    const total = this.summary?.total_tenants ?? 0;

    if (total <= 0) {
      return 0;
    }
    return Math.round((this.summary![key] / total) * 100);
  }
}
