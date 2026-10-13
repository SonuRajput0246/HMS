import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { finalize } from 'rxjs/operators';
import { passwordMatchValidator } from '../../validators/password-match.validator';
import { ISignUp } from '../../models/IAuth.model';

@Component({
  selector: 'app-sign-up',
  templateUrl: './sign-up.component.html',
  styleUrl: './sign-up.component.scss'
})
export class SignUpComponent {

  private fb = inject(FormBuilder);
  private _auth = inject(AuthService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);

  signUpForm!: FormGroup;

  hide = true;
  hideConfirm = true;
  isLoading = false;

  ngOnInit(): void {
    this.createForm();
  }

  private createForm(): void {
    this.signUpForm = this.fb.group({
      first_name: ['', [Validators.required]],
      last_name: ['', [Validators.required]],
      email: ['', [Validators.required, Validators.email]],
      new_password: ['', [Validators.required, Validators.minLength(6)]],
      confirmed_password: ['', [Validators.required]],
    },
    {
      validators: [passwordMatchValidator]
    });
  }

  togglePassword(): void {
    this.hide = !this.hide;
  }

  toggleConfirmPassword(): void {
    this.hideConfirm = !this.hideConfirm;
  }

  signUpUser(): void {
    if (this.signUpForm.invalid) {
      this.signUpForm.markAllAsTouched();
      return;
    }
    const { confirmed_password, new_password: password, ...formValue } = this.signUpForm.value;
    const payload: ISignUp = {
      ...formValue,
      password
    }
    this.isLoading = true;
    this._auth.signUp(payload)
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message!, "success");
            this._router.navigate(['/auth/otp-verification'], { state: { email: this.signUpForm.value.email, type: 'email_verification' } });
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
