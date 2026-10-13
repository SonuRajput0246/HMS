import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../../services/auth.service';
import { finalize } from 'rxjs/operators';
import { Router } from '@angular/router';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';

@Component({
  selector: 'app-forgot-password',
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.scss'
})
export class ForgotPasswordComponent {

  private _auth = inject(AuthService);
  private fb = inject(FormBuilder);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);

  forgotPasswordForm!: FormGroup;
  isLoading = false;

  ngOnInit() {
    this.createForm();
  }

  private createForm(): void {
    this.forgotPasswordForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });
  }

  get emailCtrl() {
    return this.forgotPasswordForm.get('email');
  }


  sendOtp(): void {
    if (this.forgotPasswordForm.valid) {
      const userEmail = this.forgotPasswordForm.value.email;
      console.log('Requesting OTP for:', userEmail);
      this.isLoading = true;
      this._auth.sendOtp(userEmail, 'reset_password')
        .pipe(finalize(() => {
          this.isLoading = false;
        }))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this._router.navigate(['/auth/reset-password'], { state: { email: userEmail, type: 'reset_password' } });
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to initiate reset password flow', 'error');
            }
          },
          error: (err) => {
            const errorData = err.error;
            const msg = errorData?.message || 'An error occurred while initiating reset password flow';
            this._snackbar.openSnackBar(msg, 'error');
          }
        })
    }
  }

}
