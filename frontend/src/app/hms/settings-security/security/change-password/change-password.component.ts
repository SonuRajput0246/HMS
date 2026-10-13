import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { IChangePassword } from '../../../../models/IAuth.model';
import { Router } from '@angular/router';
import { CustomSnackbarService } from '../../../../shared/custom-snackbar/custom-snackbar.service';
import { passwordDifferentValidator, passwordMatchValidator } from '../../../../validators/password-match.validator';
import { INavigationaBar } from '../../../../models/ICommon.model';
import { UserAccountService } from '../../../../services/user-account.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-change-password',
  templateUrl: './change-password.component.html',
  styleUrl: './change-password.component.scss'
})
export class ChangePasswordComponent {

  private fb = inject(FormBuilder);
  private _snackbar = inject(CustomSnackbarService);
  private _userAccountService = inject(UserAccountService);
  private _router = inject(Router);

  navData: INavigationaBar[] = [];
  changePasswordForm!: FormGroup;

  hideCurrent = true;
  hideNew = true;
  hideConfirm = true;
  isLoading = false;
  isPageLoad = false;

  // changePassObj: IChangePassword = {} as IChangePassword;

  ngOnInit(): void {
    this.initNavigation()
    this.createForm();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Settings & Security', isClickable: true, isDashboard: false, redirectValue: '/hms/settings' },
      { displayValue: 'Update Password', isClickable: false, isDashboard: false }
    ]
  }

  private createForm(): void {
    this.changePasswordForm = this.fb.group({
      current_password: ['', [Validators.required]],
      new_password: ['', [Validators.required, Validators.minLength(6)]],
      confirmed_password: ['', [Validators.required]],
    },
    { 
      validators: [passwordMatchValidator, passwordDifferentValidator]
    });
  }

  toggleCurrentPassword(): void {
    this.hideCurrent = !this.hideCurrent;
  }

  toggleNewPassword(): void {
    this.hideNew = !this.hideNew;
  }

  toggleConfirmPassword(): void {
    this.hideConfirm = !this.hideConfirm;
  }

  UpdateUserPassword(): void {
    if (this.changePasswordForm.invalid) {
      this.changePasswordForm.markAllAsTouched();
      return;
    }
    const { confirmed_password, ...payload } = this.changePasswordForm.value;
    this.isLoading = true;
    this._userAccountService.changePassword(payload)
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message!, "success");
            this._router.navigate(['/hms/settings']);
          } else {
            this._snackbar.openSnackBar(res?.message!, "error");
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A server error occurred';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }



}