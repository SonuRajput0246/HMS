import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { CommonService } from '../../../services/common.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { AuthService } from '../../../services/auth.service';
import { UserAccountService } from '../../../services/user-account.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-topnav',
  templateUrl: './topnav.component.html',
  styleUrl: './topnav.component.scss'
})
export class TopnavComponent {

  private _router = inject(Router);
  private _common = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);
  private _auth = inject(AuthService);
  private _accountService = inject(UserAccountService);

  userName = ""
  role: any;

  isPageLoad = false;

  constructor() {
      this.userName = this._common.getUserFullName();
  }

  ngOnInit() {
    this._accountService.user$.subscribe(user => {
      if (user) {
        this.userName = `${user.first_name} ${user.last_name}`;
      }
    });
    
  }

  logoutUser() {
    this.isPageLoad = true;
    document.body.classList.add('logout-blur');
    this._auth.logout()
      .pipe(finalize(() => {
        this.removeBlur();
        this.isPageLoad = false;
      }))
      .subscribe({
        next: (respdata) => {
          if (respdata && respdata.status) {
            localStorage.clear();
            sessionStorage.clear();
            this.clearStorageAndRedirectLogin();
          } else {
            this._snackbar.openSnackBar(respdata.message || 'Logout failed', 'error');
            this.clearStorageAndRedirectLogin();
          }
        },
        error: (error) => {
          this._snackbar.openSnackBar(error.message || 'An error occurred while logging out', 'error');
          this.clearStorageAndRedirectLogin();
        }
      });
  }

  private removeBlur() {
    document.body.classList.remove('logout-blur');
  }

  private clearStorageAndRedirectLogin() {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/';
  }

}
