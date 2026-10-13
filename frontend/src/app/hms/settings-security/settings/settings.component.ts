import { Component, inject, signal } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { Router } from '@angular/router';
import { CommonService } from '../../../services/common.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { AuthService } from '../../../services/auth.service';
import { finalize } from 'rxjs/operators';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss'
})
export class SettingsComponent {

  private _common = inject(CommonService);
  private _confirmService = inject(ConfirmationService);
  private _authService = inject(AuthService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);

  navData: INavigationaBar[] = [];
  
  isPageLoad = signal<boolean>(false);
  mfaEnabled = this._common.getMFAEnabledSignal();

  ngOnInit(): void {
    this.initNavigation();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Settings & Security', isClickable: false, isDashboard: false, redirectValue: '/hms/settings' }
    ];
  }

  async onDisableMFA() {
      (document.activeElement as HTMLButtonElement)?.blur();

      const result = await this._confirmService.confirm(
        'Are you sure you want to disable MFA? Your account will be less secure.'
      );

      if (result.isConfirmed) {
        this.executeDisableMFA();
      }
    }

  executeDisableMFA() {
    this.isPageLoad.set(true);
    const userId = this._common.getLoggedInUserId();

    this._authService.disableMfa(userId)
      .pipe(finalize(() => this.isPageLoad.set(false)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'MFA disabled successfully', 'success');
            this._common.setMFAEnabledStatus(false);
            this._router.navigate(['/hms/settings']);
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while disabling MFA';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }



}
