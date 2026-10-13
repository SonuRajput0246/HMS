import { Component, inject, OnInit } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { IUserProfile } from '../../../models/IAuth.model';
import { UserAccountService } from '../../../services/user-account.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { finalize } from 'rxjs/operators';
import { STORAGE_KEYS } from '../../../core/config/storage-keys';

@Component({
  selector: 'app-manage-profile',
  templateUrl: './manage-profile.component.html',
  styleUrl: './manage-profile.component.scss'
})
export class ManageProfileComponent implements OnInit {

  private fb = inject(FormBuilder);
  private _router = inject(Router);
  private _accountService = inject(UserAccountService);
  private _snackbar = inject(CustomSnackbarService);

  navData: INavigationaBar[] = [];
  profileForm!: FormGroup;
  isLoading = false;

  readonly avatar = 'assets/images/profile/Avtar_Profile2.jfif';

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.loadProfile();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Profile', isClickable: true, isDashboard: false, redirectValue: '/hms/profile' },
      { displayValue: 'Edit Profile', isClickable: false, isDashboard: false }
    ];
  }

  private createForm(): void {
    this.profileForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      // locked fields — displayed but not editable
      email: [{ value: '', disabled: true }],
      role_name: [{ value: '', disabled: true }]
    });
  }

  private loadProfile(): void {
    let user: IUserProfile = {};
    this._accountService.user$.subscribe((u) => {
      if (u) {
        user = u;
      }
    }).unsubscribe();

    if (Object.keys(user).length === 0) {
      const stored = localStorage.getItem(STORAGE_KEYS.USER_DATA);
      if (stored) {
        try {
          user = JSON.parse(stored);
        } catch {
          user = {};
        }
      }
    }

    this.profileForm.patchValue({
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      email: user.email || '',
      role_name: user.role_name || ''
    });
  }

  updateProfile(): void {
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      return;
    }

    const payload = {
      first_name: this.profileForm.get('first_name')?.value,
      last_name: this.profileForm.get('last_name')?.value
    };

    this.isLoading = true;
    this._accountService.updateUserProfile(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            // refresh the cached user so the topnav + view page update
            const currentUser = JSON.parse(localStorage.getItem(STORAGE_KEYS.USER_DATA) || '{}');
            currentUser.first_name = payload.first_name;
            currentUser.last_name = payload.last_name;
            localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(currentUser));

            this._accountService.setUser({ ...currentUser, ...payload });
            this._snackbar.openSnackBar(res.message || 'Profile updated successfully', 'success');
            this._router.navigate(['hms/profile']);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to update profile', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A server error occurred';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

}
