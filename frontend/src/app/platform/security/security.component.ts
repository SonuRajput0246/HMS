import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../models/ICommon.model';
import { IPlatformMfaSetup, IPlatformProfile } from '../models/platform.model';
import { PlatformAuthService } from '../services/platform-auth.service';

const PASSWORD_MIN = 6;
const PASSWORD_MAX = 20;

/**
 * The signed-in operator's own security settings: password and two-factor.
 *
 * Self-service only. There is no id in any call here -- the server resolves the
 * admin from the token, so this screen cannot be pointed at another account.
 *
 * MFA is compulsory for platform administrators, so this card has no way to
 * turn it off; it only reconfigures the authenticator app. The server makes
 * that safe: `setup_mfa` stores a fresh secret but leaves the account
 * un-enrolled until a code confirms it, so an abandoned attempt makes the next
 * sign-in run the compulsory setup step again instead of leaving an account
 * locked to a second factor nobody confirmed.
 */
@Component({
  selector: 'app-platform-security',
  templateUrl: './security.component.html',
  styleUrl: './security.component.scss',
})
export class PlatformSecurityComponent {

  private fb = inject(FormBuilder);
  private _auth = inject(PlatformAuthService);
  private _snackbar = inject(CustomSnackbarService);

  passwordForm!: FormGroup;
  mfaForm!: FormGroup;

  isSavingPassword = false;
  isSavingMfa = false;

  /** Enrolment payload while the confirm step is open; null when it is not. */
  mfaSetup = signal<IPlatformMfaSetup | null>(null);
  mfaEnabled = signal<boolean>(false);
  isLoading = false;

  constructor() {
    this.mfaEnabled.set(!!this._auth.profile?.mfa_enabled);
  }

  get profile(): IPlatformProfile | null {
    return this._auth.profile;
  }

  ngOnInit(): void {
    this.passwordForm = this.fb.group({
      current_password: ['', [Validators.required]],
      new_password: ['', [Validators.required, Validators.minLength(PASSWORD_MIN), Validators.maxLength(PASSWORD_MAX)]],
      confirm_password: ['', [Validators.required]],
    }, { validators: this.passwordsMatch });

    this.mfaForm = this.fb.group({
      totp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
    });

    this.refreshProfile();
  }

  private passwordsMatch(group: FormGroup) {
    const current = group.get('current_password')?.value;
    const next = group.get('new_password')?.value;
    const confirm = group.get('confirm_password')?.value;
    if (!next || !confirm) {
      return null;
    }
    if (next !== confirm) {
      return { mismatch: true };
    }
    // The server also rejects this, but catching it here saves a round trip and
    // shows the message under the field the user is looking at.
    if (current && next === current) {
      return { unchanged: true };
    }
    return null;
  }

  /** Pull the authoritative profile so the MFA state is the server's, not a
   * possibly stale copy from sign-in. */
  private refreshProfile(): void {
    this._auth.me().subscribe({
      next: (resp: IEntityResponse) => {
        if (resp?.status && resp.data) {
          const profile = resp.data as IPlatformProfile;
          this._auth.saveProfile(profile);
          this.mfaEnabled.set(!!profile.mfa_enabled);
        }
      },
      // A failed profile fetch is not worth interrupting the screen for; the
      // cached value stands and every action still goes through the server.
      error: () => {},
    });
  }

  changePassword(): void {
    if (this.passwordForm.invalid || this.isSavingPassword) {
      this.passwordForm.markAllAsTouched();
      return;
    }

    this.isSavingPassword = true;
    this._auth.changePassword({
      current_password: this.passwordForm.value.current_password,
      new_password: this.passwordForm.value.new_password,
    })
      .pipe(finalize(() => (this.isSavingPassword = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this._snackbar.openSnackBar(resp?.message || 'Password updated.', 'success');
          this.passwordForm.reset();
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'Could not update the password.', 'error');
        },
      });
  }

  beginMfaSetup(): void {
    if (this.isSavingMfa) {
      return;
    }
    this.isSavingMfa = true;
    this._auth.setupMfa()
      .pipe(finalize(() => (this.isSavingMfa = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          if (resp?.status && resp.data) {
            this.mfaForm.reset();
            this.mfaSetup.set(resp.data as IPlatformMfaSetup);
          } else {
            this._snackbar.openSnackBar(resp?.message || 'Could not start enrolment.', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'Could not start enrolment.', 'error');
        },
      });
  }

  confirmMfa(): void {
    if (this.mfaForm.invalid || this.isSavingMfa) {
      this.mfaForm.markAllAsTouched();
      return;
    }

    this.isSavingMfa = true;
    this._auth.enableMfa({ totp: this.mfaForm.value.totp })
      .pipe(finalize(() => (this.isSavingMfa = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this._snackbar.openSnackBar(resp?.message || 'Two-factor authentication is on.', 'success');
          this.mfaEnabled.set(true);
          this.mfaSetup.set(null);
          this.refreshProfile();
        },
        error: (err) => {
          this._snackbar.openSnackBar(err?.error?.message || 'Invalid code.', 'error');
          this.mfaForm.get('totp')?.reset();
        },
      });
  }

  cancelMfaSetup(): void {
    this.mfaSetup.set(null);
    this.mfaForm.reset();
  }

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
}
