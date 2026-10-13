import { Component, inject, signal } from '@angular/core';
import { INavigationaBar } from '../../../../models/ICommon.model';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonService } from '../../../../services/common.service';
import { AuthService } from '../../../../services/auth.service';
import { finalize } from 'rxjs';
import { CustomSnackbarService } from '../../../../shared/custom-snackbar/custom-snackbar.service';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';

@Component({
  selector: 'app-mfa',
  templateUrl: './mfa.component.html',
  styleUrl: './mfa.component.scss'
})
export class MfaComponent {

  private _router = inject(Router);
  private fb = inject(FormBuilder);
  private _common = inject(CommonService);
  private _authService = inject(AuthService);
  private _snackbar = inject(CustomSnackbarService);

  navData: INavigationaBar[] = [];
  isLoading: Boolean = false;
  isPageLoad = signal<boolean>(false);
  isLoadingSignal = signal<boolean>(false);

  mfaOtpForm!: FormGroup;

  qr_uri = signal<string>('');
  secret = signal<string>('');
  otpCode = signal<string>('');

  ngOnInit(): void {
    this.initNavigation();
    this.loadInitialData();
    this.mfaOtpForm = this.fb.group({
      totp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]]
    });
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Settings & Security', isClickable: true, isDashboard: false, redirectValue: '/hms/settings' },
      { displayValue: 'Setup Multi Factor Authentication', isClickable: false, isDashboard: false }
    ]
  }

  private loadInitialData(): void {
    this.isPageLoad.set(true);
    const userId = this._common.getLoggedInUserId();

    this._authService.initiateEnableMfa(userId)
      .pipe(finalize(() => this.isPageLoad.set(false)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.qr_uri.set(res.data.qr_uri || '');
            this.secret.set(res.data.secret || '');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching MFA data';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }


  verifyAndEnableMfa(): void {
    if (this.mfaOtpForm.invalid) {
      this.mfaOtpForm.markAllAsTouched();
      return;
    }
    this.isPageLoad.set(true);
    const userId = this._common.getLoggedInUserId();
    const payload = {
      userId: userId,
      totp: this.mfaOtpForm.value.totp
    };

    this._authService.verifyOrEnableMfa(payload)
      .pipe(finalize(() => this.isPageLoad.set(false)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'MFA enabled successfully', 'success');
            this._common.setMFAEnabledStatus(true);
            this._router.navigate(['/hms/settings']);
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while enabling MFA';
          this._snackbar.openSnackBar(msg, 'error');
          this.mfaOtpForm.get('totp')?.reset();
        }
      });
  }

  onCancel(): void {
    this._router.navigate(['/hms/settings']);
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
