import { Component, Inject, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../../models/ICommon.model';
import { ITenant } from '../../models/platform.model';
import { PlatformTenantService } from '../../services/platform-tenant.service';

/** The same 6..20 window the server enforces. */
const PASSWORD_MIN = 6;
const PASSWORD_MAX = 20;

/**
 * Reset a hotel's own super admin (recovery).
 *
 * The hotel cannot do this for itself: the account lives inside the tenant, so
 * when its only administrator loses the password there is nobody who could reset
 * it from the inside. The operator sets a new one here, and the server revokes
 * that admin's live sessions so the reset is not cosmetic.
 *
 * Deliberately separate from the platform console's own
 * `admins/<id>/reset-password`: that one resets a *console* operator and refuses
 * your own account, while this one resets a *hotel* admin and is the only route
 * to it.
 */
@Component({
  selector: 'app-reset-hotel-admin-password-dialog',
  templateUrl: './reset-admin-password-dialog.component.html',
  styleUrl: './reset-admin-password-dialog.component.scss',
})
export class ResetHotelAdminPasswordDialogComponent {

  private fb = inject(FormBuilder);
  private _tenants = inject(PlatformTenantService);
  private _snackbar = inject(CustomSnackbarService);

  form!: FormGroup;
  isSaving = false;

  constructor(
    private _dialogRef: MatDialogRef<ResetHotelAdminPasswordDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public tenant: ITenant
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      new_password: [
        '',
        [Validators.required, Validators.minLength(PASSWORD_MIN), Validators.maxLength(PASSWORD_MAX)],
      ],
      confirm_password: ['', [Validators.required]],
    }, { validators: this.passwordsMatch });
  }

  private passwordsMatch(group: FormGroup) {
    const password = group.get('new_password')?.value;
    const confirm = group.get('confirm_password')?.value;
    return password && confirm && password === confirm ? null : { mismatch: true };
  }

  save(): void {
    if (this.form.invalid || this.isSaving) {
      this.form.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    this._tenants.resetAdminPassword(this.tenant.id, this.form.value.new_password)
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this._snackbar.openSnackBar(resp?.message || 'Password reset.', 'success');
          this._dialogRef.close(true);
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'Could not reset the password.', 'error');
        },
      });
  }

  cancel(): void {
    this._dialogRef.close(false);
  }
}
