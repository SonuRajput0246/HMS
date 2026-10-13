import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { UserAccountService } from '../../services/user-account.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { finalize } from 'rxjs/operators';
import { AuthService } from '../../services/auth.service';
import { InstanceService } from '../../core/config/instance.service';
import { STORAGE_KEYS } from '../../core/config/storage-keys';

@Component({
  selector: 'app-otp-verification',
  templateUrl: './otp-verification.component.html',
  styleUrl: './otp-verification.component.scss'
})
export class OtpVerificationComponent {

  private fb = inject(FormBuilder);
  private _router = inject(Router);
  private _accountService = inject(UserAccountService);
  private _snackbar = inject(CustomSnackbarService);
  private _auth = inject(AuthService);
  private _instance = inject(InstanceService);

  otpForm!: FormGroup;
  isLoading = false;
  isPageLoad = false;
  email: string = '';
  flowType: string = '';

  timerSeconds = 60;
  timerInterval: any;
  canResend = false;

  constructor() {
    const navigation = this._router.getCurrentNavigation();
    const state = navigation?.extras.state as { email: string; type: string };
    if (!state || !state.email) {
      this._router.navigate(['/auth/login']);
      return;
    }
    this.email = state.email;
    this.flowType = state.type;
  }

  ngOnInit(): void {
    this.otpForm = this.fb.group({
      otp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]]
    });
    this.startTimer();
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
            // the old code is dead — clear it so the user types the new one.
            // reset() also drops touched/pristine state, so the field shows no
            // "required" error until they focus it.
            this.otpForm.get('otp')?.reset();
          }
        },
        error: (err) => this._snackbar.openSnackBar(err.error?.message || 'Failed to resend OTP', 'error')
      });
  }

  verifyOtp(): void {
    if (this.otpForm.invalid) return;

    this.isLoading = true;
    const payload = {
      email: this.email,
      otp: this.otpForm.value.otp
    };

    if (this.flowType === 'account_activation') {
      this._auth.activateAccount(payload)
        .pipe(finalize(() => this.isLoading = false))
        .subscribe({
          next: (res) => {
            if (res.status) {
              this.handleLoginSuccess(res.data, this.flowType);
            } else {
              this._snackbar.openSnackBar(res.message || 'Invalid OTP', 'error');
            }
          },
          error: (err) => {
            this._snackbar.openSnackBar(err.error?.message || 'Account activation failed', 'error');
          }
        });
    } else if (this.flowType === 'email_verification') {
      this._auth.verifyEmail(payload)
        .pipe(finalize(() => this.isLoading = false))
        .subscribe({
          next: (res) => {
            if (res.status) {
              this.handleLoginSuccess(res.data, this.flowType);
            } else {
              this._snackbar.openSnackBar(res.message || 'Invalid OTP', 'error');
            }
          },
          error: (err) => {
            this._snackbar.openSnackBar(err.error?.message || 'Email verification failed', 'error');
          }
        });
    } else {
      this.isLoading = false;
      this._snackbar.openSnackBar('Invalid flow type', 'error');
      this._router.navigate(['/auth/login'])
    }
  }

  ngOnDestroy(): void {
    if (this.timerInterval) clearInterval(this.timerInterval);
  }

  private handleLoginSuccess(data: any, flowType: string): void {
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token);
    localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(data));
    this._snackbar.openSnackBar(flowType === 'account_activation' ? 'Account Activated Successfully!' : 'Email Verified Successfully!', 'success');
    this._router.navigateByUrl(this._instance.homeUrl);
  }








}
