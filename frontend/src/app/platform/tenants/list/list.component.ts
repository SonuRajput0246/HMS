import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { MatPaginatorSelectConfig, PageEvent } from '@angular/material/paginator';
import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { finalize } from 'rxjs/operators';

import { ConfirmationService } from '../../../services/confirmation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { PAGE_SIZE_SELECT_CONFIG } from '../../../shared/paginator-config';
import { IEntityResponse } from '../../../models/ICommon.model';
import { ITenant } from '../../models/platform.model';
import { PlatformConfigService } from '../../services/platform-config.service';
import { PlatformTenantService } from '../../services/platform-tenant.service';
import { ResetHotelAdminPasswordDialogComponent } from '../reset-admin-password-dialog/reset-admin-password-dialog.component';

/**
 * Every hotel on the platform, with the lifecycle verbs the operator owns.
 *
 * The status facet mirrors the backend's three views (`active` / `inactive` /
 * `archived`) rather than two boolean filters, so a tab maps to exactly one
 * request parameter and an impossible combination cannot be expressed.
 *
 * `inactive` and `archived` are separate here for the same reason they are
 * separate flags on the backend. Deactivation stops a hotel trading but leaves
 * it on every list; archiving takes it off the lists and its subdomain stops
 * resolving, without destroying anything. Collapsing them into one "disabled"
 * switch would make two differently-reversible actions look interchangeable.
 *
 * Destructive verbs go through a confirmation, and the reason is the product one
 * -- deactivating bites on the next request, archiving hides the hotel -- not a
 * formality.
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
  private _dialog = inject(MatDialog);

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
  // option list are sized identically across the app and the platform console.
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
            err?.error?.message || 'Could not load hotels.',
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
    this._router.navigate(['/platform/tenants/new']);
  }

  editTenant(tenant: ITenant): void {
    this._router.navigate(['/platform/tenants', tenant.id, 'edit']);
  }

  async toggleStatus(tenant: ITenant): Promise<void> {
    const activating = !tenant.is_active;
    const result = await this._confirm.confirm(
      activating ? 'Activate hotel?' : 'Deactivate hotel?',
      activating
        ? `"${tenant.name}" and its users will be able to sign in again.`
        : `"${tenant.name}" will stop accepting sign-ins immediately. Its data is untouched.`,
      activating ? 'Yes, activate' : 'Yes, deactivate'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.run(tenant, this._tenants.setStatus(tenant.id, activating));
  }

  async archiveTenant(tenant: ITenant): Promise<void> {
    const result = await this._confirm.confirm(
      'Archive hotel?',
      `"${tenant.name}" will be hidden and unreachable at its subdomain. ` +
        `Nothing is deleted -- you can restore it later.`,
      'Yes, archive'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.run(tenant, this._tenants.archive(tenant.id));
  }

  async restoreTenant(tenant: ITenant): Promise<void> {
    const result = await this._confirm.confirm(
      'Restore hotel?',
      `"${tenant.name}" will come back inactive. Activate it when you are ` +
        `ready for it to trade again.`,
      'Yes, restore'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.run(tenant, this._tenants.restore(tenant.id));
  }

  /**
   * Reset a hotel's own administrator. The one recovery a hotel cannot perform
   * itself -- when its only admin loses the password there is nobody inside to
   * do it -- so the dialog collects a new one and warns that the target is
   * signed out everywhere.
   */
  resetAdminPassword(tenant: ITenant): void {
    this._dialog.open(ResetHotelAdminPasswordDialogComponent, {
      data: tenant,
      autoFocus: 'first-tabbable',
    })
      .afterClosed()
      .subscribe((changed: boolean) => {
        if (changed) {
          this.loadTenants();
        }
      });
  }

  /** One lifecycle verb, with the row lock and the reload/refill handled. */
  private run(tenant: ITenant, request$: Observable<IEntityResponse>): void {
    this.busyTenantId = tenant.id;
    request$
      .pipe(finalize(() => (this.busyTenantId = null)))
      .subscribe({
        next: (resp: IEntityResponse) => this.afterMutation(resp),
        error: (err: any) => this.reportFailure(err),
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
