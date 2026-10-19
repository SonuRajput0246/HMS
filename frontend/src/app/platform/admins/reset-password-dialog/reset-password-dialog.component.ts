import { Component, Inject, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../../models/ICommon.model';
import { ISuperAdmin } from '../../models/platform.model';
import { PlatformAdminService } from '../../services/platform-admin.service';

/**
 * Reset another administrator's password (recovery).
 *
 * Deliberately separate from the self-service change: this path does not ask
 * for the current password, because the admin performing it does not know it,
 * and the server refuses it on your own account for exactly that reason. The
 * target is signed out everywhere once it succeeds.
 */
@Component({
  selector: 'app-reset-password-dialog',
  templateUrl: './reset-password-dialog.component.html',
  styleUrl: './reset-password-dialog.component.scss',
})
export class ResetPasswordDialogComponent {

  private fb = inject(FormBuilder);
  private _admins = inject(PlatformAdminService);
  private _snackbar = inject(CustomSnackbarService);

  form!: FormGroup;
  isSaving = false;

  constructor(
    private _dialogRef: MatDialogRef<ResetPasswordDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public admin: ISuperAdmin
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      new_password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(20)]],
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
    this._admins.resetPassword(this.admin.id, this.form.value.new_password)
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
