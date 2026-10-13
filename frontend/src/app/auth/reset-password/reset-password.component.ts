import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { IResetPassword } from '../../models/IAuth.model';
import { passwordMatchValidator } from '../../validators/password-match.validator';
import { finalize } from 'rxjs/operators';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
@Component({
  selector: 'app-reset-password',
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss'
})
export class ResetPasswordComponent {
  private fb = inject(FormBuilder);
  private _auth = inject(AuthService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  resetPasswordForm!: FormGroup;
  hideNew = true;
  hideConfirm = true;
  isLoading = false;
  email: string = '';
  flowType: string = '';
  timerSeconds = 60;
  timerInterval: any;
  canResend = false;

  constructor() {
    const navigation = this._router.getCurrentNavigation();
    const state = navigation?.extras.state as { email: string, type: string };
    if (!state || !state.email) {
      this._router.navigate(['/auth/login']);
      return;
    }
    this.email = state.email;
    this.flowType = state.type;
  }
  ngOnInit(): void {
    this.createForm();
    this.startTimer();
  }
  private createForm(): void {
    this.resetPasswordForm = this.fb.group({
      otp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
      new_password: ['', [Validators.required, Validators.minLength(6)]],
      confirmed_password: ['', [Validators.required]],
    },
    {
      validators: [passwordMatchValidator]
    });
  }
  toggleNewPassword(): void {
    this.hideNew = !this.hideNew;
  }
  toggleConfirmPassword(): void {
    this.hideConfirm = !this.hideConfirm;
  }
  startTimer(): void {
    this.canResend = false;
    this.timerSeconds = 60;
    this.timerInterval = setInterval(() => {
      this.timerSeconds--;
      if (this.timerSeconds === 0) {
        this.canResend = true;
        clearInterval(this.timerInterval);
      }
    }, 1000);
  }
  allowOnlyNumbers(event: KeyboardEvent) {
    const charCode = event.which ?? event.keyCode;
    if (charCode < 48 || charCode > 57) {
      event.preventDefault();
    }
  }
  onOtpPaste(event: ClipboardEvent) {
    const pasted = event.clipboardData?.getData('text') ?? '';
    if (!/^\d+$/.test(pasted)) {
      event.preventDefault();
    }
  }
  resendOtp(): void {
    if (!this.canResend) return;
    this.isLoading = true;
    this._auth.sendOtp(this.email, this.flowType)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res.status) {
            this._snackbar.openSnackBar('OTP Resent Successfully', 'success');
            this.startTimer();
            // the old code is dead — clear just the OTP so the user types the
            // new one. The password fields are left untouched so they don't
            // have to retype them. reset() also drops touched/pristine state,
            // so the field shows no "required" error until they focus it.
            this.resetPasswordForm.get('otp')?.reset();
          }
        },
        error: (err) => this._snackbar.openSnackBar(err.error?.message || 'Failed to resend OTP', 'error')
      });
  }
  ngOnDestroy(): void {
    if (this.timerInterval) clearInterval(this.timerInterval);
  }
  resetUserPassword(): void {
    if (this.resetPasswordForm.invalid) {
      this.resetPasswordForm.markAllAsTouched();
      return;
    }
    const { confirmed_password, new_password: password, ...formValue } = this.resetPasswordForm.value;
    const payload: IResetPassword = {
      email: this.email,
      ...formValue,
      password
    }
    this.isLoading = true;
    this._auth.resetPassword(payload)
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message!, "success");
            this._router.navigate(['/auth/login']);
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
