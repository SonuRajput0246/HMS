import { Component, inject } from '@angular/core';
import { FormBuilder, FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { IEnumOption, INavigationaBar } from '../../../models/ICommon.model';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { debounceTime, finalize } from 'rxjs/operators';
import { CommonService } from '../../../services/common.service';
import { ReservationService } from '../../../services/reservation.service';

@Component({
  selector: 'app-advance-payment',
  templateUrl: './advance-payment.component.html',
  styleUrl: './advance-payment.component.scss'
})
export class AdvancePaymentComponent {

  private fb = inject(FormBuilder);
  private _reservationService = inject(ReservationService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);
  private _commonService = inject(CommonService);

  navData: INavigationaBar[] = [];
  paymentForm!: FormGroup;
  breakpoint = 3;

  isLoading = false;
  isPageLoad = false;
  isCurrencyLoading = false;
  isPaymentMethodLoading = false;
  isPaymentStatusLoading = false;

  currencyList: any[] = [];
  currencySearchCtrl = new FormControl('');

  /**
   * Payment method and status come from the enum_definitions / enum_options
   * tables rather than a hardcoded list, so adding an option in the admin UI
   * shows up on this form without a frontend change. `option_key` is the exact
   * string written back to `payments.payment_method` / `payment_status`.
   */
  paymentMethodList: IEnumOption[] = [];
  paymentStatusList: IEnumOption[] = [];

  reservationId: number | null = null;


  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.onResize();

    this.reservationId = Number(this.AR.snapshot.paramMap.get('reservationId'));

    this.getAllCurrencies();
    this.currencySearchCtrl.valueChanges
      .pipe(
        debounceTime(400)
      )
      .subscribe(search => {
        this.getAllCurrencies(search || '');
      });

    this.fetchEnumOptions('payment_method', 'paymentMethodList', 'isPaymentMethodLoading', 'payment methods');
    this.fetchEnumOptions('payment_status', 'paymentStatusList', 'isPaymentStatusLoading', 'payment statuses');
  }

  initNavigation() {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: true, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Advance Payment', isClickable: false, isDashboard: false}
    ]
  }

  onResize() {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }

  createForm() {
    this.paymentForm = this.fb.group({
      amount: ['', [Validators.required, Validators.min(1)]],
      currency: ['INR', Validators.required],
      payment_method: ['cash', Validators.required],
      payment_status: ['pending', Validators.required],
      transaction_ref: [''],
      remark: [''],
      payment_date: [new Date(), Validators.required],
      notes: ['']
    });
  }


  getAllCurrencies(searchValue: string = ''): void {
    this.isCurrencyLoading = true;
    this._commonService.getCurrenciesList({"search_value": searchValue})
      .pipe(finalize(() => this.isCurrencyLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.currencyList = res?.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch currencies', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while fetching currencies';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }




  /**
   * Loads one enum's options into `listProp` and flips `loadingProp` while in
   * flight. Shared by payment method and status, which differ only by enum key.
   */
  fetchEnumOptions(
    enumKey: string,
    listProp: 'paymentMethodList' | 'paymentStatusList',
    loadingProp: 'isPaymentMethodLoading' | 'isPaymentStatusLoading',
    label: string
  ): void {
    this[loadingProp] = true;
    this._commonService.getEnumOptions(enumKey)
      .pipe(finalize(() => this[loadingProp] = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this[listProp] = res.data || [];
            this.applyEnumDefault(enumKey, this[listProp]);
          } else {
            this._snackbar.openSnackBar(res?.message || `Failed to fetch ${label}`, 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || `An error occurred while fetching ${label}`;
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }


  /** True while either enum-backed dropdown is still populating. */
  get isEnumLoading(): boolean {
    return this.isPaymentMethodLoading || this.isPaymentStatusLoading;
  }


  /**
   * Preselects the option the enum marks as default, and clears a value the
   * enum no longer offers.
   *
   * The reset matters: the control starts as `'cash'` / `'pending'`, and an
   * admin can deactivate or rename those options. A stale value left in the
   * select is invisible in the UI but still submitted, and `payment_status` is
   * rejected by the API with a 400 naming every value it does accept.
   */
  private applyEnumDefault(controlName: string, options: IEnumOption[]): void {
    const control = this.paymentForm.get(controlName);
    if (!control) {
      return;
    }

    const selected = control.value;
    if (selected && options.some(option => option.option_key === selected)) {
      return;
    }

    const fallback = options.find(option => option.is_default) || options[0];
    control.setValue(fallback ? fallback.option_key : '');
  }


  finalSubmit(): void {
    if (this.paymentForm.invalid) {
      console.log("in");
      
      this.paymentForm.markAllAsTouched();
      return;
    }

    const payload = {
      ...this.paymentForm.value,
      reservation_id: this.reservationId,
      payment_type: 'advance',
      is_deleted: false
    };
    this.isLoading = true;
    this._reservationService.insertPaymentDetails(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Reservation created successfully.', 'success')
            this._router.navigate(['hms/reservations'])
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save payment', 'error')
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving payment';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

}
