import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { UserAccountService } from '../../../../services/user-account.service';
import { CustomSnackbarService } from '../../../../shared/custom-snackbar/custom-snackbar.service';
import { IEnumOption, INavigationaBar } from '../../../../models/ICommon.model';
import { finalize } from 'rxjs/operators';
import { ConfirmationService } from '../../../../services/confirmation.service';
import { CommonService } from '../../../../services/common.service';

/**
 * `option_key` of the option meaning "I'll describe it myself". Selecting it
 * swaps the free-text box in, and its contents become the stored reason.
 *
 * Compared as a key rather than the 'Other' label: the label is data an admin can
 * edit, and a renamed option would silently stop routing to the free-text branch
 * and store the literal string "Other" as the reason instead.
 */
const OTHER_REASON_KEY = 'other';

@Component({
  selector: 'app-delete-account',
  templateUrl: './delete-account.component.html',
  styleUrl: './delete-account.component.scss'
})
export class DeleteAccountComponent {

  private fb = inject(FormBuilder);
  private _accountService = inject(UserAccountService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _commonService = inject(CommonService);

  navData: INavigationaBar[] = [];
  deleteAccountReasonForm!: FormGroup;
  deleteAccountSecurityForm!: FormGroup;

  hidePassword = true;
  isLoading = false;

  /** Read from `enum_options`, so an admin can add or retire a reason. */
  deletionReasonList: IEnumOption[] = [];
  isReasonLoading = false;

  ngOnInit(): void {
    this.initNavigation()
    this.createForm();
    this.loadDeletionReasons();
  }

  private loadDeletionReasons(): void {
    this.isReasonLoading = true;
    this._commonService.getEnumOptions('account_deletion_reason')
      .pipe(finalize(() => this.isReasonLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.deletionReasonList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch deletion reasons', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching deletion reasons';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  /** Drives the free-text box: visible only while 'Other' is selected. */
  get isOtherReasonSelected(): boolean {
    return this.deleteAccountReasonForm.get('deletion_reason')?.value === OTHER_REASON_KEY;
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Settings & Security', isClickable: true, isDashboard: false, redirectValue: '/hms/settings' },
      { displayValue: 'Delete Account', isClickable: false, isDashboard: false }
    ]
  }

  private createForm(): void {
    this.deleteAccountReasonForm = this.fb.group({
      // Named to match DeleteMyAccountSchema.deletion_reason, which the service
      // reads. This control was `deleted_reason`, which BaseSchema drops as an
      // unknown field, so the chosen reason never reached account_deletions.reason.
      deletion_reason: [''],
      other_reason: [''],
    });
    this.deleteAccountSecurityForm = this.fb.group({
      password: ['', [Validators.required]]
    });
  }

  togglePassword(): void {
    this.hidePassword = !this.hidePassword;
  }

  openAccountDeletionDialog(): void {
    if (this.deleteAccountSecurityForm.invalid) {
      this.deleteAccountSecurityForm.markAllAsTouched();
      return;
    }
    (document.activeElement as HTMLElement)?.blur();

    this._confirmService.confirmDelete('Are you sure you want to delete your account?').then((result) => {
      if (result.isConfirmed) {
        this.prepareAndSubmit();
      }
    });
  }

  private prepareAndSubmit(): void {
    const { deletion_reason, other_reason } = this.deleteAccountReasonForm.value;
    const { password } = this.deleteAccountSecurityForm.value;
    const payload = {
      deletion_reason: deletion_reason === OTHER_REASON_KEY ? other_reason : deletion_reason,
      password: password
    };
    this.submitAccountDeletion(payload);
  }

  private submitAccountDeletion(payload: any): void {
    this.isLoading = true;
    this._accountService.deleteAccount(payload)
      .pipe(
        // finalize always runs when the observable completes or errors
        finalize(() => this.isLoading = false) 
      )
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.clearSessionAndRedirect();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Action failed', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A server error occurred';
          this._snackbar.openSnackBar(msg, 'error');
          // No need to set isLoading = false here anymore!
        }
      });
  }


  private clearSessionAndRedirect(): void {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/';
  }


}