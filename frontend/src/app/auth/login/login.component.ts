import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { AuthService } from '../../services/auth.service';
import { finalize } from 'rxjs/operators';
import { ConfirmationService } from '../../services/confirmation.service';
import { CommonService } from '../../services/common.service';
import { InstanceService } from '../../core/config/instance.service';
import { STORAGE_KEYS } from '../../core/config/storage-keys';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent {

  private fb = inject(FormBuilder);
  private _auth = inject(AuthService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _confirmService = inject(ConfirmationService);
  private _common = inject(CommonService);
  private _instance = inject(InstanceService);

  loginForm!: FormGroup;
  verifyMfaForm!: FormGroup;
  hidePassword = true;
  isLoading = false;
  isPageLoad = false;

  loginStage = signal<'credentials' | 'mfa'>('credentials');
  otpCode = signal<string>('');
  // private tempUserId: number | null = null;
  private tempMfaToken: string = '';

  ngOnInit() {
    this.createForm();
  }

  private createForm(): void {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  private createMfaForm(): void {
    this.verifyMfaForm = this.fb.group({
      totp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]]
    });
  }

  togglePasswordHide(): void {
    this.hidePassword = !this.hidePassword;
  }


  LoginUser(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }
    this.isLoading = true;
    this.isPageLoad = true;
    this._auth.login(this.loginForm.value)
      .pipe(finalize(() => {
        this.isLoading = false;
        this.isPageLoad = false;
      }))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            if (res.data?.mfa_enabled) {
              // this.tempMfaToken = res.data.temp_token;
              this.tempMfaToken = res.data.temp_token;
              this.loginStage.set('mfa');
              this.createMfaForm();
              this._snackbar.openSnackBar('Please enter your 6-digit MFA code', 'info');
            } else {
              this.handleLoginSuccess(res.data);
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Login failed', 'error');
          }
        },
        error: (err) => this.handleLoginError(err)
      })
  }

  verifyMfaLogin(): void {
    if (this.verifyMfaForm.invalid) {
      this.verifyMfaForm.markAllAsTouched();
      return;
    }

    if (!this.tempMfaToken) {
      this._snackbar.openSnackBar('Session expired. Please login again.', 'error');
      this.loginStage.set('credentials');
      return;
    }
    this.isLoading = true;
    this.isPageLoad = true;
    
    const payload = {
      temp_token: this.tempMfaToken,
      totp: this.verifyMfaForm.value.totp
    };
    
    this._auth.verifyTotpLogin(payload)
      .pipe(finalize(() => {
        this.isLoading = false;
        this.isPageLoad = false;
      }))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.handleLoginSuccess(res.data);
            this.tempMfaToken = '';
          } else {
            this._snackbar.openSnackBar(res?.message || 'Invalid MFA code', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'MFA verification failed', 'error');
          this.verifyMfaForm.get('totp')?.reset();
        }
      });
  }

  private handleLoginSuccess(data: any): void {
    sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token);
    localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(data));
    this._common.setMFAEnabledStatus(data.mfa_enabled); //check this by commenting (cookie is set)
    this._snackbar.openSnackBar(`Welcome to ${this._instance.label}`, 'success');
    this._router.navigateByUrl(this._instance.homeUrl);
  }

  private handleLoginError(err: any): void {
    const errorData = err.error;
    const msg = errorData?.message || 'An error occurred while logging in';
    if (err.status === 403 && errorData?.ask_account_activation) {
      this.handleInactiveAccount(msg);
    } else if (err.status === 403 && errorData?.start_email_verification) {
      this._router.navigate(['/auth/otp-verification'], { state: { email: this.loginForm.value.email, type: 'email_verification' } });
    }
    else {
      this._snackbar.openSnackBar(msg, 'error');
    }
  }

  private handleInactiveAccount(serverMessage: string): void {
    this._confirmService.confirm(
      serverMessage,
      'Would you like to activate it now?',
      'Yes, Activate'
    ).then((result) => {
      if (result.isConfirmed) {
        this.isPageLoad = true;
        this._auth.sendOtp(this.loginForm.value.email, 'account_activation')
          .pipe(finalize(() => {
            this.isPageLoad = false;
          }))
          .subscribe({
            next: (res) => {
              if (res?.status) {
                this._router.navigate(['/auth/otp-verification'], { state: { email: this.loginForm.value.email, type: 'account_activation' } });
              } else {
                this._snackbar.openSnackBar(res?.message || 'Failed to initiate account activation flow', 'error');
              }
            },
            error: (err) => {
              const errorData = err.error;
              const msg = errorData?.message || 'An error occurred while initiating account activation flow';
              this._snackbar.openSnackBar(msg, 'error');
            }
          })
      }
    });
  }


  get passwordHasError(): boolean {
    const ctrl = this.loginForm.get('password');
    return !!(ctrl && ctrl.invalid && (ctrl.touched || ctrl.dirty));
  }

  resetToCredentials() {
    this.loginStage.set('credentials');
    this.otpCode.set('');
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


}