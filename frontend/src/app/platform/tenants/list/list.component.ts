import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { MatPaginatorSelectConfig, PageEvent } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';

import { ConfirmationService } from '../../../services/confirmation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { PAGE_SIZE_SELECT_CONFIG } from '../../../shared/paginator-config';
import { IEntityResponse } from '../../../models/ICommon.model';
import { ITenant } from '../../models/platform.model';
import { PlatformConfigService } from '../../services/platform-config.service';
import { PlatformTenantService } from '../../services/platform-tenant.service';

/**
 * Every workspace on the platform, with the lifecycle verbs the operator owns.
 *
 * The status facet mirrors the backend's three views (`active` / `inactive` /
 * `archived`) rather than two boolean filters, so a tab maps to exactly one
 * request parameter and an impossible combination cannot be expressed.
 *
 * Destructive verbs go through a confirmation, and the reason is the product
 * one -- deactivating bites on the next request, archiving hides the cafe --
 * not a formality.
 */
@Component({
  selector: 'app-tenant-list',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss',
})
export class TenantListComponent {

  private _tenants = inject(PlatformTenantService);
  private _config = inject(PlatformConfigService);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);
  private _confirm = inject(ConfirmationService);

  readonly displayedColumns = [
    'name',
    'slug',
    'timezone',
    'currency',
    'user_count',
    'status',
    'actions',
  ];

  // Shared with every other list page, so the page-size trigger and its
  // option list are sized identically across the HMS and the platform console.
  readonly pageSizeSelect: MatPaginatorSelectConfig = PAGE_SIZE_SELECT_CONFIG;

  tenants: ITenant[] = [];
  totalRecords = 0;
  pageSize = 10;
  pageIndex = 0;
  statusFilter = '';
  searchValue = '';

  isLoading = false;

  /**
   * A refetch while rows are already on screen. Those rows are kept (dimmed)
   * and the spinner floats over them, instead of the whole card being covered
   * by the full-loading veil -- which made a filter click look like a reload.
   */
  get isRefreshing(): boolean {
    return this.isLoading && this.tenants.length > 0;
  }

  /** The tenant a lifecycle call is in flight for, so only its row is locked. */
  busyTenantId: number | null = null;

  /**
   * What every slug in the Subdomain column is suffixed with, e.g.
   * `localhost:4200`. Comes from the deployment (`PUBLIC_BASE_URL` on the
   * server), never from a literal in this file.
   */
  get hostSuffix(): string {
    return this._config.tenantHostSuffix;
  }

  ngOnInit(): void {
    this.loadTenants();
  }

  loadTenants(): void {
    this.isLoading = true;
    this._tenants.list({
      page_size: this.pageSize,
      page_number: this.pageIndex + 1,
      search_value: this.searchValue.trim() || undefined,
      status: this.statusFilter || undefined,
    })
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.tenants = (resp?.data as ITenant[]) ?? [];
          this.totalRecords = resp?.meta?.total_records ?? 0;
        },
        error: (err) => {
          this.tenants = [];
          this.totalRecords = 0;
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not load tenants.',
            'error'
          );
        },
      });
  }

  onSearch(): void {
    this.pageIndex = 0;
    this.loadTenants();
  }

  onStatusChange(status: string): void {
    this.statusFilter = status ?? '';
    this.pageIndex = 0;
    this.loadTenants();
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadTenants();
  }

  /** First letter for the row avatar. Falls back rather than rendering blank. */
  initial(name: string): string {
    return (name ?? '').trim().charAt(0).toUpperCase() || '?';
  }

  createTenant(): void {
    this._router.navigate(['/tenants/new']);
  }

  editTenant(tenant: ITenant): void {
    this._router.navigate(['/tenants', tenant.id, 'edit']);
  }

  async toggleStatus(tenant: ITenant): Promise<void> {
    const activating = !tenant.is_active;
    const result = await this._confirm.confirm(
      activating ? 'Activate tenant?' : 'Deactivate tenant?',
      activating
        ? `"${tenant.name}" and its users will be able to sign in again.`
        : `"${tenant.name}" will stop accepting sign-ins immediately. Its data is untouched.`,
      activating ? 'Yes, activate' : 'Yes, deactivate'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.busyTenantId = tenant.id;
    this._tenants.setStatus(tenant.id, activating)
      .pipe(finalize(() => (this.busyTenantId = null)))
      .subscribe({
        next: (resp) => this.afterMutation(resp),
        error: (err) => this.reportFailure(err),
      });
  }

  async archiveTenant(tenant: ITenant): Promise<void> {
    const result = await this._confirm.confirm(
      'Archive tenant?',
      `"${tenant.name}" will be hidden and unreachable at its subdomain. ` +
        `Nothing is deleted -- you can restore it later.`,
      'Yes, archive'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.busyTenantId = tenant.id;
    this._tenants.archive(tenant.id)
      .pipe(finalize(() => (this.busyTenantId = null)))
      .subscribe({
        next: (resp) => this.afterMutation(resp),
        error: (err) => this.reportFailure(err),
      });
  }

  async restoreTenant(tenant: ITenant): Promise<void> {
    const result = await this._confirm.confirm(
      'Restore tenant?',
      `"${tenant.name}" will come back inactive. Activate it when you are ` +
        `ready for it to trade again.`,
      'Yes, restore'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.busyTenantId = tenant.id;
    this._tenants.restore(tenant.id)
      .pipe(finalize(() => (this.busyTenantId = null)))
      .subscribe({
        next: (resp) => this.afterMutation(resp),
        error: (err) => this.reportFailure(err),
      });
  }

  private afterMutation(resp: IEntityResponse): void {
    this._snackbar.openSnackBar(resp?.message || 'Done.', 'success');
    this.loadTenants();
  }

  private reportFailure(err: any): void {
    this._snackbar.openSnackBar(err?.error?.message || 'Action failed.', 'error');
  }
}
