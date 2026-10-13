import { Component, inject } from '@angular/core';
import { IEnumOption, INavigationaBar } from '../../../../models/ICommon.model';
import { FormBuilder, FormGroup } from '@angular/forms';
import { UserAccountService } from '../../../../services/user-account.service';
import { CustomSnackbarService } from '../../../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../../../services/confirmation.service';
import { CommonService } from '../../../../services/common.service';
import { finalize } from 'rxjs/operators';

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
  selector: 'app-deactivate-account',
  templateUrl: './deactivate-account.component.html',
  styleUrl: './deactivate-account.component.scss'
})
export class DeactivateAccountComponent {

  private fb = inject(FormBuilder);
  private _accountService = inject(UserAccountService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _commonService = inject(CommonService);

  navData: INavigationaBar[] = [];
  deactivateForm!: FormGroup;

  isLoading = false;

  /** Read from `enum_options`, so an admin can add or retire a reason. */
  deactivationReasonList: IEnumOption[] = [];
  isReasonLoading = false;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.loadDeactivationReasons();
  }

  private loadDeactivationReasons(): void {
    this.isReasonLoading = true;
    this._commonService.getEnumOptions('account_deactivation_reason')
      .pipe(finalize(() => this.isReasonLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.deactivationReasonList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch deactivation reasons', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching deactivation reasons';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  /** Drives the free-text box: visible only while 'Other' is selected. */
  get isOtherReasonSelected(): boolean {
    return this.deactivateForm.get('deactivation_reason')?.value === OTHER_REASON_KEY;
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Settings & Security', isClickable: true, isDashboard: false, redirectValue: '/hms/settings' },
      { displayValue: 'Deactivate Account', isClickable: false, isDashboard: false }
    ]
  }

  private createForm(): void {
    this.deactivateForm = this.fb.group({
      deactivation_reason: [''],
      other_reason: ['']
    });
  }

  openDeactivateDialog() {
    (document.activeElement as HTMLElement)?.blur();
    this._confirmService.confirmDelete('Are you sure you want to deactivate your account?').then((result) => {
      if (result.isConfirmed) {
        this.prepareAndSubmit();
      }
    });
  }


  private prepareAndSubmit(): void {
    const { deactivation_reason, other_reason } = this.deactivateForm.value;
    const payload = {
      deactivation_reason: deactivation_reason === OTHER_REASON_KEY ? other_reason : deactivation_reason
    };
    this.submitDeactivation(payload);
  }

  private submitDeactivation(payload: any) {
    this.isLoading = true;
    this._accountService.deactivateAccount(payload)
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (res) => {
        if (res && res.status) {
          this.clearSessionAndRedirect();
        } else {
          this._snackbar.openSnackBar(res?.message || 'Deactivation failed', 'error');
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