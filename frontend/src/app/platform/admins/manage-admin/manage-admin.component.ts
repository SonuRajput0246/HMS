import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../../models/ICommon.model';
import { IAuditLog, ISuperAdmin } from '../../models/platform.model';
import { PlatformAdminService } from '../../services/platform-admin.service';
import { PlatformAuditService } from '../../services/platform-audit.service';

/** Longest the accounts table allows; the server enforces the same window. */
const PASSWORD_MIN = 6;
const PASSWORD_MAX = 20;

/**
 * Create or edit a platform operator, as a page rather than a dialog.
 *
 * One screen for both: the fields are the same and only the password (create
 * only) and the submit call differ, so a second near-identical component would
 * be a copy to keep in step. The API call lives here rather than in the list so
 * a validation failure from the server leaves the form populated with its input
 * intact; the list rebuilds itself from scratch when the operator navigates
 * back, so it does not need telling that something changed.
 *
 * The shape is the tenant screen's (`manage-tenant`) reduced to one entity: a
 * create has no history to show, an edit appends the operator's own audit trail
 * below the form.
 */
@Component({
  selector: 'app-manage-admin',
  templateUrl: './manage-admin.component.html',
  styleUrl: './manage-admin.component.scss',
})
export class ManageAdminComponent {

  private fb = inject(FormBuilder);
  private _route = inject(ActivatedRoute);
  private _router = inject(Router);
  private _admins = inject(PlatformAdminService);
  private _audit = inject(PlatformAuditService);
  private _snackbar = inject(CustomSnackbarService);

  form!: FormGroup;
  adminId: number | null = null;
  isLoading = false;
  isSaving = false;

  /** This operator's own audit trail, newest first. Populated only when
   * editing, since a brand-new operator has no history to show. */
  adminHistory: IAuditLog[] = [];
  isHistoryLoading = false;
  historyTotal = 0;

  get isEdit(): boolean {
    return this.adminId !== null;
  }

  ngOnInit(): void {
    const idParam = this._route.snapshot.paramMap.get('id');
    this.adminId = idParam ? Number(idParam) : null;

    this.buildForm();

    if (this.adminId !== null) {
      this.loadAdmin(this.adminId);
    }
  }

  private buildForm(): void {
    const controls: Record<string, unknown> = {
      first_name: ['', [Validators.required, Validators.maxLength(50)]],
      last_name: ['', [Validators.required, Validators.maxLength(50)]],
      email: ['', [Validators.required, Validators.email, Validators.maxLength(255)]],
    };

    if (!this.isEdit) {
      controls['password'] = [
        '',
        [Validators.required, Validators.minLength(PASSWORD_MIN), Validators.maxLength(PASSWORD_MAX)],
      ];
      controls['confirm_password'] = ['', [Validators.required]];
    }

    this.form = this.fb.group(controls, this.isEdit ? {} : { validators: this.passwordsMatch });
  }

  /** Create only: the two password boxes must agree before the call is made. */
  private passwordsMatch(group: FormGroup) {
    const password = group.get('password')?.value;
    const confirm = group.get('confirm_password')?.value;
    return password && confirm && password === confirm ? null : { mismatch: true };
  }

  private loadAdmin(id: number): void {
    this.isLoading = true;
    this._admins.get(id)
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          const admin = resp?.data as ISuperAdmin | null;
          if (!admin) {
            return;
          }
          this.form.patchValue({
            first_name: admin.first_name,
            last_name: admin.last_name,
            email: admin.email,
          });
          this.loadHistory();
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not load the administrator.',
            'error'
          );
          this.goBack();
        },
      });
  }

  /**
   * The newest few audit rows for this operator. Supplementary: a failure here
   * is swallowed rather than raising a snackbar, because it must never block
   * editing the operator itself.
   */
  private loadHistory(): void {
    if (this.adminId === null) {
      return;
    }
    this.isHistoryLoading = true;
    this._audit.list({
      page_size: 6,
      page_number: 1,
      entity_type: 'super_admin',
      entity_id: this.adminId,
    })
      .pipe(finalize(() => (this.isHistoryLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.adminHistory = (resp?.data as IAuditLog[]) ?? [];
          this.historyTotal = resp?.meta?.total_records ?? 0;
        },
        error: () => {
          this.adminHistory = [];
          this.historyTotal = 0;
        },
      });
  }

  /** Opens the full feed, already scoped to this operator. */
  viewFullHistory(): void {
    this._router.navigate(['/platform/activity'], {
      queryParams: { entity_type: 'super_admin', entity_id: this.adminId },
    });
  }

  /** One-line summary of a row's `details`, for the compact list. */
  historySummary(log: IAuditLog): string {
    if (!log.details) {
      return '';
    }
    try {
      const parsed = JSON.parse(log.details);
      if (parsed && typeof parsed === 'object') {
        if (parsed.changed) {
          return Object.keys(parsed.changed).join(', ');
        }
        return Object.keys(parsed).join(', ');
      }
      return String(parsed);
    } catch {
      return log.details;
    }
  }

  save(): void {
    if (this.form.invalid || this.isSaving) {
      this.form.markAllAsTouched();
      return;
    }

    const value = this.form.value;
    this.isSaving = true;

    const request$: Observable<IEntityResponse> = this.isEdit
      ? this._admins.update(this.adminId as number, {
          first_name: value.first_name,
          last_name: value.last_name,
          email: value.email,
        })
      : this._admins.create({
          first_name: value.first_name,
          last_name: value.last_name,
          email: value.email,
          password: value.password,
        });

    request$
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (resp) => {
          this._snackbar.openSnackBar(resp?.message || 'Saved.', 'success');
          this.goBack();
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not save the administrator.',
            'error'
          );
        },
      });
  }

  goBack(): void {
    this._router.navigate(['/platform/admins']);
  }
}
