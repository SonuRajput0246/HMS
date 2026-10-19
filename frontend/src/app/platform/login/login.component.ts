import { Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../models/ICommon.model';
import { IPlatformLoginData, IPlatformMfaChallenge, IPlatformMfaSetup } from '../models/platform.model';
import { PlatformAuthService } from '../services/platform-auth.service';

/**
 * Platform sign-in. Deliberately not the hotel login with a different logo:
 * it talks to `/api/v1/platform/auth/login`, writes the `platform_*` keys and
 * lands on `/platform/dashboard`. The hotel screen does none of those, and the
 * two must never be reachable from each other's host -- see the `canMatch` host
 * split in app-routing.module.ts.
 *
 * Three stages. Credentials first, then the second factor -- and because MFA
 * is compulsory for platform administrators, that second factor has two shapes:
 * enter the code (account already enrolled) or scan the QR and enter a code
 * from the app just scanned (account that has never enrolled).
 *
 * Neither of the latter two carries a session: the first response returns only
 * a short-lived token that unlocks `/auth/verify-mfa` and nothing else, so a
 * client that ignored the flag still cannot reach the console. The token is
 * what ties the code to *this* password attempt.
 */
@Component({
  selector: 'app-platform-login',
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class PlatformLoginComponent {

  private fb = inject(FormBuilder);
  private _auth = inject(PlatformAuthService);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);

  loginForm!: FormGroup;
  verifyMfaForm!: FormGroup;
  hidePassword = true;
  isLoading = false;

  loginStage = signal<'credentials' | 'mfa' | 'setup'>('credentials');
  /** The QR + secret that arrives with the challenge when the account has
   * never enrolled. Present only on the `setup` stage. */
  mfaSetup = signal<IPlatformMfaSetup | null>(null);
  private tempMfaToken = '';

  @ViewChild('emailInput') private _emailInput?: ElementRef<HTMLInputElement>;
  @ViewChild('passwordInput') private _passwordInput?: ElementRef<HTMLInputElement>;

  ngOnInit(): void {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  togglePasswordHide(): void {
    this.hidePassword = !this.hidePassword;
  }

  /**
   * Browser autofill writes straight into the inputs and never dispatches
   * `input`, so Angular's reactive controls never hear about it and keep their
   * initial empty value. Validating the model alone would therefore reject a
   * perfectly good saved-credential login as blank -- and, worse, report
   * "Email is required" under a field the user can plainly see is filled.
   *
   * So the DOM is treated as the source of truth at submit time. For anything
   * the user actually typed this is a no-op: `formControlName` keeps the input
   * and the control in step.
   */
  private syncFromDom(): void {
    this.loginForm.patchValue({
      email: this._emailInput?.nativeElement.value ?? '',
      password: this._passwordInput?.nativeElement.value ?? '',
    });
  }

  LoginUser(): void {
    // Read the inputs back before trusting the model. See syncFromDom().
    this.syncFromDom();

    if (this.loginForm.invalid || this.isLoading) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.isLoading = true;
    this._auth.login(this.loginForm.value)
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          if (!resp?.status) {
            this._snackbar.openSnackBar(resp?.message || 'Login failed.', 'error');
            return;
          }

          // A challenge carries `mfa_required` and no session: show the second
          // step. Anything else is a finished login.
          const data = resp.data as IPlatformMfaChallenge;
          if (data?.mfa_required && data?.temp_token) {
            this.tempMfaToken = data.temp_token;
            this.verifyMfaForm = this.fb.group({
              totp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
            });

            // Compulsory MFA. An account that has never enrolled is sent the
            // QR and secret on this same response, so the token that proves
            // the password is what unlocks them and no one can read a secret
            // for an account whose password they did not just present.
            if (data.mfa_setup_required) {
              this.mfaSetup.set({ qr_uri: data.qr_uri ?? '', secret: data.secret ?? '' });
              this.loginStage.set('setup');
              this._snackbar.openSnackBar(
                'Two-factor authentication is required. Set it up to continue.',
                'info'
              );
              return;
            }

            this.mfaSetup.set(null);
            this.loginStage.set('mfa');
            this._snackbar.openSnackBar('Enter the 6-digit code from your authenticator app.', 'info');
            return;
          }

          this.saveSession(resp.data as IPlatformLoginData);
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Unable to sign in. Please try again.',
            'error'
          );
        },
      });
  }

  verifyMfaLogin(): void {
    if (this.isLoading) {
      return;
    }
    if (this.verifyMfaForm.invalid) {
      this.verifyMfaForm.markAllAsTouched();
      return;
    }
    if (!this.tempMfaToken) {
      this._snackbar.openSnackBar('Your session expired. Please sign in again.', 'error');
      this.resetToCredentials();
      return;
    }

    this.isLoading = true;
    this._auth.verifyMfa({
      temp_token: this.tempMfaToken,
      totp: this.verifyMfaForm.value.totp,
    })
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          if (resp?.status && resp.data) {
            this.tempMfaToken = '';
            this.saveSession(resp.data as IPlatformLoginData);
          } else {
            this._snackbar.openSnackBar(resp?.message || 'Invalid code.', 'error');
            this.verifyMfaForm.get('totp')?.reset();
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'Verification failed.', 'error');
          this.verifyMfaForm.get('totp')?.reset();
        },
      });
  }

  resetToCredentials(): void {
    this.tempMfaToken = '';
    this.mfaSetup.set(null);
    this.loginStage.set('credentials');
  }

  /** Copy the manual entry key, for anyone whose camera will not scan the QR. */
  copySecret(): void {
    const secret = this.mfaSetup()?.secret;
    if (!secret) {
      return;
    }
    navigator.clipboard?.writeText(secret).then(
      () => this._snackbar.openSnackBar('Secret copied.', 'success'),
      () => this._snackbar.openSnackBar('Could not copy the secret.', 'error')
    );
  }

  private saveSession(data: IPlatformLoginData): void {
    this._auth.saveSession(data);
    this._snackbar.openSnackBar('Signed in.', 'success');
    this._router.navigate(['/platform/dashboard']);
  }
}
