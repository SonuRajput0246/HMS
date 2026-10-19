import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { MatPaginatorSelectConfig, PageEvent } from '@angular/material/paginator';
import { MatDialog } from '@angular/material/dialog';
import { finalize } from 'rxjs/operators';

import { ConfirmationService } from '../../../services/confirmation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { PAGE_SIZE_SELECT_CONFIG } from '../../../shared/paginator-config';
import { IEntityResponse } from '../../../models/ICommon.model';
import { ISuperAdmin } from '../../models/platform.model';
import { PlatformAdminService } from '../../services/platform-admin.service';
import { PlatformAuthService } from '../../services/platform-auth.service';
import { ResetPasswordDialogComponent } from '../reset-password-dialog/reset-password-dialog.component';

/**
 * The platform's own operators.
 *
 * The status facet mirrors the backend's two views (active / inactive). An
 * operator cannot deactivate or reset their own account -- the server refuses
 * it, and this screen disables those verbs on the signed-in admin's row so the
 * refusal is never the first the operator hears of it.
 *
 * Create and edit are pages of their own (`admins/new`, `admins/:id/edit`), so
 * this screen only navigates to them; the list is rebuilt when the operator
 * comes back, which is how a change becomes visible here.
 */
@Component({
  selector: 'app-admin-list',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss',
})
export class AdminListComponent {

  private _admins = inject(PlatformAdminService);
  private _auth = inject(PlatformAuthService);
  private _router = inject(Router);
  private _dialog = inject(MatDialog);
  private _confirm = inject(ConfirmationService);
  private _snackbar = inject(CustomSnackbarService);

  readonly displayedColumns = ['admin', 'mfa', 'status', 'last_password_update_at', 'actions'];

  // Shared with every other list page, so the page-size trigger and its
  // option list are sized identically across the hotel app and the platform console.
  readonly pageSizeSelect: MatPaginatorSelectConfig = PAGE_SIZE_SELECT_CONFIG;

  admins: ISuperAdmin[] = [];
  totalRecords = 0;
  pageSize = 10;
  pageIndex = 0;
  statusFilter = '';
  searchValue = '';
  isLoading = false;

  get isRefreshing(): boolean {
    return this.isLoading && this.admins.length > 0;
  }

  /** The signed-in operator, so their own row can disable the self-targeting
   * verbs before the server has to. */
  get currentAdminId(): number | null {
    return this._auth.profile?.id ?? null;
  }

  busyAdminId: number | null = null;

  ngOnInit(): void {
    this.loadAdmins();
  }

  loadAdmins(): void {
    this.isLoading = true;
    this._admins.list({
      page_size: this.pageSize,
      page_number: this.pageIndex + 1,
      search_value: this.searchValue.trim() || undefined,
      status: this.statusFilter || undefined,
    })
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.admins = (resp?.data as ISuperAdmin[]) ?? [];
          this.totalRecords = resp?.meta?.total_records ?? 0;
        },
        error: (err) => {
          this.admins = [];
          this.totalRecords = 0;
          this._snackbar.openSnackBar(err?.error?.message || 'Could not load administrators.', 'error');
        },
      });
  }

  onSearch(): void {
    this.pageIndex = 0;
    this.loadAdmins();
  }

  onStatusChange(status: string): void {
    this.statusFilter = status ?? '';
    this.pageIndex = 0;
    this.loadAdmins();
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadAdmins();
  }

  initial(admin: ISuperAdmin): string {
    return (admin.first_name ?? '').trim().charAt(0).toUpperCase() || '?';
  }

  isSelf(admin: ISuperAdmin): boolean {
    return this.currentAdminId === admin.id;
  }

  /** True while a brute-force lockout is still in force. */
  isLocked(admin: ISuperAdmin): boolean {
    return !!admin.locked_until && new Date(admin.locked_until).getTime() > Date.now();
  }

  createAdmin(): void {
    this._router.navigate(['/platform/admins/new']);
  }

  editAdmin(admin: ISuperAdmin): void {
    this._router.navigate(['/platform/admins', admin.id, 'edit']);
  }

  resetPassword(admin: ISuperAdmin): void {
    this._dialog.open(ResetPasswordDialogComponent, {
      data: admin,
      autoFocus: 'first-tabbable',
    })
      .afterClosed()
      .subscribe((changed: boolean) => {
        if (changed) {
          this.loadAdmins();
        }
      });
  }

  async resetMfa(admin: ISuperAdmin): Promise<void> {
    const result = await this._confirm.confirm(
      'Reset two-factor authentication?',
      `${admin.email} will be signed out and must scan a new authenticator app at their next sign-in.`,
      'Yes, reset'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.busyAdminId = admin.id;
    this._admins.resetMfa(admin.id)
      .pipe(finalize(() => (this.busyAdminId = null)))
      .subscribe({
        next: (resp) => this.afterMutation(resp),
        error: (err) => this.reportFailure(err),
      });
  }

  async toggleStatus(admin: ISuperAdmin): Promise<void> {
    const activating = !admin.is_active;
    const result = await this._confirm.confirm(
      activating ? 'Activate administrator?' : 'Deactivate administrator?',
      activating
        ? `${admin.email} will be able to sign in to the platform console again.`
        : `${admin.email} will be signed out and blocked from the platform console immediately.`,
      activating ? 'Yes, activate' : 'Yes, deactivate'
    );
    if (!result.isConfirmed) {
      return;
    }

    this.busyAdminId = admin.id;
    this._admins.setStatus(admin.id, activating)
      .pipe(finalize(() => (this.busyAdminId = null)))
      .subscribe({
        next: (resp) => this.afterMutation(resp),
        error: (err) => this.reportFailure(err),
      });
  }

  private afterMutation(resp: IEntityResponse): void {
    this._snackbar.openSnackBar(resp?.message || 'Done.', 'success');
    this.loadAdmins();
  }

  private reportFailure(err: any): void {
    this._snackbar.openSnackBar(err?.error?.message || 'Action failed.', 'error');
  }
}
