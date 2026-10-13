import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { AbstractControl, FormArray, FormBuilder, FormControl, FormGroup, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, of, Subscription } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, finalize, switchMap } from 'rxjs/operators';
import { IEnumOption, INavigationaBar } from '../../../models/ICommon.model';
import {
  IAvailableRooms,
  IInsertPaymentPayload,
  IReservationPayment,
  IUpdateReservationPayload
} from '../../../models/IReservation.model';
import { CommonService } from '../../../services/common.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { GuestService } from '../../../services/guest.service';
import { ReservationService } from '../../../services/reservation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { minAgeValidator } from '../../../validators/minAgeValidator';
interface CanDeactivate {
  canDeactivate(): boolean | Promise<boolean>;
}
/**
 * Age bands used to bucket the guest roster into the reservation's
 * adults / children / infants counts. Adjust to match your hotel's policy.
 */
const INFANT_MAX_AGE = 2;
const CHILD_MAX_AGE = 12;
type SectionState = 'idle' | 'saving' | 'saved' | 'error';
interface IPaymentTypeOption {
  value: string;
  label: string;
}
/**
 * Frozen and module-level so the option objects handed to `*ngFor` keep a
 * stable identity. A fresh array of fresh literals per change-detection pass
 * makes the select rebuild its options forever.
 */
const PAYMENT_TYPE_OPTIONS: ReadonlyArray<IPaymentTypeOption> = Object.freeze([
  Object.freeze({ value: 'advance', label: 'Advance' }),
  Object.freeze({ value: 'additional_advance', label: 'Additional Advance' })
]);
/**
 * `min` is an input of `MatDatepickerInput` (the `[matDatepicker]` directive on
 * the input), and the panel's calendar picks it up through
 * `MatDatepickerBase._getMinDate()` — so past days are already unselectable in
 * the UI. This group validator is the backstop for what the calendar cannot
 * police: a stale row, or a value set programmatically.
 */
function stayWindowValidator(checkInKey: string, checkOutKey: string): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const checkIn = group.get(checkInKey)?.value;
    const checkOut = group.get(checkOutKey)?.value;
    if (!checkIn || !checkOut) return null;
    const start = new Date(checkIn).setHours(0, 0, 0, 0);
    const end = new Date(checkOut).setHours(0, 0, 0, 0);
    const today = new Date().setHours(0, 0, 0, 0);
    if (end <= start) return { stayWindow: true };
    if (end < today) return { stayWindowInPast: true };
    return null;
  };
}
@Component({
  selector: 'app-edit-reservation',
  templateUrl: './edit-reservation.component.html',
  styleUrl: './edit-reservation.component.scss'
})
export class EditReservationComponent implements OnInit, OnDestroy, CanDeactivate {
  private fb = inject(FormBuilder);
  private _reservationService = inject(ReservationService);
  private _guestService = inject(GuestService);
  private _commonService = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);
  // ---------------------------------------------------------------
  //  Reservation-level data
  // ---------------------------------------------------------------
  navData: INavigationaBar[] = [];
  reservationId = 0;
  reservation: any = null;
  isLoading = false;
  /** DOB picker ceiling — today, so nobody picks a future birth date */
  readonly maxDob = new Date();
  // ---------------------------------------------------------------
  //  Forms
  // ---------------------------------------------------------------
  stayForm!: FormGroup;
  guestForm!: FormGroup;
  paymentForm!: FormGroup;
  // ---------------------------------------------------------------
  //  Lookup data
  // ---------------------------------------------------------------
  countryList: any[] = [];
  stateList: any[] = [];
  cityList: any[] = [];
  currencyList: any[] = [];
  countrySearchCtrl = new FormControl('');
  stateSearchCtrl = new FormControl('');
  citySearchCtrl = new FormControl('');
  currencySearchCtrl = new FormControl('');
  isCountryLoading = false;
  isStateLoading = false;
  isCityLoading = false;
  isCurrencyLoading = false;
  /**
   * Enum-backed dropdowns, read from the `enum_definitions` / `enum_options`
   * tables so an option added in the admin UI appears here without a frontend
   * change. `option_key` is the exact string stored on the column.
   *
   * `gender` / `idType` are shared by the primary guest and every companion in
   * `additionalGuests`, so both read the same list.
   */
  genderList: IEnumOption[] = [];
  idTypeList: IEnumOption[] = [];
  paymentMethodList: IEnumOption[] = [];
  paymentStatusList: IEnumOption[] = [];
  isGenderLoading = false;
  isIdTypeLoading = false;
  isPaymentMethodLoading = false;
  isPaymentStatusLoading = false;
  // ---------------------------------------------------------------
  //  Room picker — paginated, searchable, bounded height
  // ---------------------------------------------------------------
  showRoomPicker = false;
  isAvailabilityLoading = false;
  availableRooms: IAvailableRooms[] = [];
  availabilityChecked = false;
  selectedRoom: IAvailableRooms | null = null;
  readonly roomPageSize = 10;
  roomPageNumber = 1;
  roomTotalDocs = 0;
  roomSearchCtrl = new FormControl('');
  roomTypeFilterCtrl = new FormControl('all');
  get roomTypeFilter(): string {
    return String(this.roomTypeFilterCtrl.value || 'all');
  }
  // ---------------------------------------------------------------
  //  Payment ledger
  // ---------------------------------------------------------------
  payments: IReservationPayment[] = [];
  showPaymentForm = false;
  isSavingPayment = false;
  /**
   * The payment type is not a free choice. The first advance is collected once
   * at booking, so before it exists only `advance` is offered; once it has been
   * recorded every subsequent payment is an `additional_advance`. Offering both
   * would let a second `advance` be saved, which the ledger cannot represent.
   *
   * A field rather than a getter on purpose. A getter that builds a new array
   * of new option objects returns a different reference every change-detection
   * pass, so `ngFor` tears down and rebuilds every `mat-option` each time,
   * which re-notifies the select and re-enters detection -- the page locks up
   * the moment the form renders. The array identity has to be stable across
   * passes, so it is recomputed only when `payments` actually changes.
   */
  availablePaymentTypes: IPaymentTypeOption[] = [PAYMENT_TYPE_OPTIONS[0]];
  /**
   * Recompute the allowed set from the ledger and keep the control on a legal
   * value. A control left on a now-invalid option would fail the `required`
   * check against a detached option, or send a second `advance`.
   */
  private refreshPaymentTypes(): void {
    const hasAdvance = this.payments.some(p => String(p.payment_type) === 'advance');
    this.availablePaymentTypes = [hasAdvance ? PAYMENT_TYPE_OPTIONS[1] : PAYMENT_TYPE_OPTIONS[0]];
    const control = this.paymentForm.get('payment_type');
    if (control && !this.availablePaymentTypes.some(o => o.value === control.value)) {
      control.setValue(this.availablePaymentTypes[0].value);
    }
  }
  // ---------------------------------------------------------------
  //  Save state
  // ---------------------------------------------------------------
  isSavingRoom = false;
  isSavingGuest = false;
  isSavingAll = false;
  roomState: SectionState = 'idle';
  guestState: SectionState = 'idle';
  /** guest identity fields — frozen once the guest has arrived */
  private readonly identityFields = [
    'first_name', 'last_name', 'gender', 'date_of_birth', 'id_type', 'id_number'
  ];
  private roomDirty = false;
  private guestDirty = false;
  private roomSnapshot = '';
  private guestSnapshot = '';
  private suppressDirtyCheck = false;
  private subs = new Subscription();
  // ---------------------------------------------------------------
  //  Status locks — business rules
  // ---------------------------------------------------------------
  /** Stay is over / booking abandoned — nothing editable */
  readonly readOnlyStatuses = ['checked_out', 'cancelled', 'no_show'];
  /** Stay has started — dates can no longer move */
  readonly dateLockedStatuses = ['checked_in', 'checked_out'];
  /** Identity is frozen once the guest has physically arrived */
  readonly identityLockedStatuses = ['checked_in', 'checked_out'];
  get status(): string {
    return String(this.reservation?.reservation_status || '').toLowerCase();
  }
  get isReadOnly(): boolean {
    return this.readOnlyStatuses.includes(this.status);
  }
  get areDatesLocked(): boolean {
    return this.isReadOnly || this.dateLockedStatuses.includes(this.status);
  }
  get isIdentityLocked(): boolean {
    return this.isReadOnly || this.identityLockedStatuses.includes(this.status);
  }
  get isRoomDirty(): boolean {
    return this.roomDirty;
  }
  get isGuestDirty(): boolean {
    return this.guestDirty;
  }
  get hasUnsavedChanges(): boolean {
    return this.roomDirty || this.guestDirty;
  }
  get canSaveAll(): boolean {
    return !this.isReadOnly && (this.roomDirty || this.guestDirty) && !this.isSavingAll;
  }
  // ---------------------------------------------------------------
  //  Date guards
  // ---------------------------------------------------------------
  /** midnight today — the floor for any newly picked date */
  get today(): Date {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }
  /**
   * Past days are not selectable. Note this only restricts what can be
   * *picked* — a stale `reserved` booking whose check-in already lapsed
   * keeps its stored value and can still be moved forward.
   */
  get minCheckInDate(): Date {
    return this.today;
  }
  /**
   * Earliest legal check-out for a given check-in: the day after it, and never
   * a past date. Shared by the calendar floor and the auto-correct so the two
   * can never disagree.
   */
  private earliestLegalCheckout(checkIn: Date): Date {
    const earliest = new Date(checkIn);
    earliest.setDate(earliest.getDate() + 1);
    return earliest > this.today ? earliest : this.today;
  }
  /**
   * Check-out can never precede check-in. A same-day selection is not
   * offered because it yields a 0-night stay (nights drive the total);
   * drop the `+ 1` if day-use bookings are valid for you.
   */
  get minCheckOutDate(): Date {
    const checkIn = this.toDate(this.stayForm?.get('check_in_date')?.value);
    return checkIn ? this.earliestLegalCheckout(checkIn) : this.today;
  }
  // ---------------------------------------------------------------
  //  Derived stay / money values
  // ---------------------------------------------------------------
  get totalNights(): number {
    const { check_in_date, check_out_date } = this.stayForm?.getRawValue() || {};
    if (!check_in_date || !check_out_date) return 0;
    const diff = new Date(check_out_date).getTime() - new Date(check_in_date).getTime();
    return diff > 0 ? Math.round(diff / 86400000) : 0;
  }
  get pricePerNight(): number {
    return this.selectedRoom?.price ?? this.reservation?.room?.price ?? 0;
  }
  /** auto total — ignored while a manual override is active */
  get computedTotal(): number {
    return this.totalNights * (Number(this.pricePerNight) || 0);
  }
  get effectiveTotal(): number {
    if (this.stayForm?.get('total_amount_override')?.value) {
      return Number(this.stayForm.get('total_amount')?.value) || 0;
    }
    return this.computedTotal;
  }
  get paidAmount(): number {
    return this.payments.reduce((sum, p) => sum + this.signedAmount(p), 0);
  }
  get balanceAmount(): number {
    return this.effectiveTotal - this.paidAmount;
  }
  get isOverCollected(): boolean {
    return this.balanceAmount < 0;
  }
  /**
   * Occupancy is derived from the guest roster, never entered separately.
   * The primary guest is one adult; each additional guest is bucketed by age.
   * A single source of truth means editing the roster cannot drift out of
   * sync with the stored reservation counts.
   */
  get guestCounts(): { adults: number; children: number; infants: number } {
    let adults = 1;   // the primary guest
    let children = 0;
    let infants = 0;
    const roster = this.guestForm?.get('additional_guests') as FormArray | null;
    for (const ctrl of roster?.controls || []) {
      const age = Number(ctrl.get('age')?.value);
      if (age >= 1 && age <= INFANT_MAX_AGE) infants++;
      else if (age > INFANT_MAX_AGE && age <= CHILD_MAX_AGE) children++;
      else adults++;   // an unset age counts as adult until it is corrected
    }
    return { adults, children, infants };
  }
  get occupancyLabel(): string {
    const { adults, children, infants } = this.guestCounts;
    const parts: string[] = [];
    if (adults) parts.push(`${adults} adult${adults > 1 ? 's' : ''}`);
    if (children) parts.push(`${children} child${children > 1 ? 'ren' : ''}`);
    if (infants) parts.push(`${infants} infant${infants > 1 ? 's' : ''}`);
    return parts.join(', ');
  }
  /** infants do not occupy a bed, so capacity is adults + children */
  get guestOccupancy(): number {
    const { adults, children } = this.guestCounts;
    return adults + children;
  }
  get roomCapacity(): number {
    const room: any = this.selectedRoom || this.reservation?.room;
    return (Number(room?.max_adults) || 0) + (Number(room?.max_children) || 0);
  }
  get isOverCapacity(): boolean {
    const capacity = this.roomCapacity;
    return capacity > 0 && this.guestOccupancy > capacity;
  }
  get selectedRoomNumber(): string {
    return this.selectedRoom?.room_number || this.reservation?.room?.room_number || '—';
  }
  get selectedRoomType(): string {
    return this.selectedRoom?.room_type || this.reservation?.room?.room_type || '—';
  }
  // ===============================================================
  //  Lifecycle
  // ===============================================================
  ngOnInit(): void {
    this.initNavigation();
    this.createForms();
    this.wireFormEvents();
    this.reservationId = Number(this.AR.snapshot.paramMap.get('reservationId'));
    if (!this.reservationId) {
      this.onBack();
      return;
    }
    this.getAllCountries();
    this.loadEnumOptions();
    this.loadReservation();
  }
  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }
  initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Edit Reservation', isClickable: false, isDashboard: false }
    ];
  }
  private wireFormEvents(): void {
    // stay form: live totals + dirty flag
    this.subs.add(this.stayForm.valueChanges.subscribe(() => {
      this.refreshAutoTotal();
      this.syncRoomDirty();
    }));
    // A check-in moved forward can strand the check-out behind it. Push the
    // check-out to the earliest legal day rather than leaving an error the
    // user has to reason about.
    this.subs.add(this.stayForm.get('check_in_date')!.valueChanges.subscribe(() => {
      this.enforceCheckoutAfterCheckin();
    }));
    // re-check availability whenever the stay window moves
    this.subs.add(this.stayForm.get('check_in_date')!.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(() => this.checkAvailability()));
    this.subs.add(this.stayForm.get('check_out_date')!.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(() => this.checkAvailability()));
    this.subs.add(this.guestForm.valueChanges.subscribe(() => this.syncGuestDirty()));
    this.subs.add(this.countrySearchCtrl.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(search => this.getAllCountries(search || '')));
    this.subs.add(this.stateSearchCtrl.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(search => this.getAllStates(Number(this.guestForm.value.state_id) || 0, search || '')));
    this.subs.add(this.citySearchCtrl.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(search => this.getAllCities(Number(this.guestForm.value.city_id) || 0, search || '')));
    this.subs.add(this.currencySearchCtrl.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(search => this.getAllCurrencies(search || '')));
    this.subs.add(this.roomSearchCtrl.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(() => this.onRoomSearch()));
  }
  // ===============================================================
  //  Forms
  // ===============================================================
  private createForms(): void {
    this.stayForm = this.fb.group({
      check_in_date: [null, Validators.required],
      check_out_date: [null, Validators.required],
      room_id: [null, Validators.required],
      // occupancy is NOT here — it is derived from the guest roster via
      // guestCounts so the two can never drift apart
      total_amount_override: [false],
      total_amount: [0, [Validators.required, Validators.min(0)]],
      total_amount_override_reason: ['']
    }, { validator: stayWindowValidator('check_in_date', 'check_out_date') });
    this.guestForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      gender: ['', Validators.required],
      date_of_birth: [null, [Validators.required, minAgeValidator(18)]],
      email: ['', [Validators.required, Validators.email]],
      phone_number: ['', Validators.required],
      address: [''],
      city_id: [{ value: '', disabled: true }, Validators.required],
      state_id: [{ value: '', disabled: true }, Validators.required],
      country_id: ['', Validators.required],
      nationality_id: ['', Validators.required],
      id_type: ['', Validators.required],
      id_number: ['', Validators.required],
      notes: [''],
      vip_status: [false],
      blacklist_status: [false],
      is_active: [true],
      additional_guests: this.fb.array([])
    });
    this.paymentForm = this.fb.group({
      payment_type: ['advance', Validators.required],
      amount: [null, [Validators.required, Validators.min(0.01)]],
      currency: ['INR', Validators.required],
      payment_method: ['cash', Validators.required],
      payment_status: ['success', Validators.required],
      paid_at: [new Date(), Validators.required],
      transaction_ref: [''],
      remarks: ['']
    });
    // seed the control off the same constant the options list uses, so the
    // initial value can never be one the dropdown is not offering
    this.refreshPaymentTypes();
  }
  get additionalGuests(): FormArray {
    return this.guestForm.get('additional_guests') as FormArray;
  }
  // ===============================================================
  //  Load
  // ===============================================================
  private loadReservation(): void {
    this.isLoading = true;
    this._reservationService.getReservationById(this.reservationId)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) {
            this.reservation = res.data;
            this.patchStayForm();
            this.patchPayments();
            this.loadGuest();
            this.applyStatusLocks();
            this.checkAvailability();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch reservation', 'error');
          }
        },
        error: (err: any) => {
          const msg = err?.error?.message || 'An error occurred while fetching reservation';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }
  private patchStayForm(): void {
    const r = this.reservation;
    const room: any = r.room || {};
    // Rate fallback: older get-by-id responses have no `room.price`, so derive
    // it from the stored total instead of showing a 0 total.
    const storedTotal = Number(r.total_amount) || 0;
    const checkIn = this.toDate(r.check_in_date);
    const checkOut = this.toDate(r.check_out_date);
    const storedNights = checkIn && checkOut
      ? Math.round((checkOut.getTime() - checkIn.getTime()) / 86400000)
      : 0;
    const price = Number(room.price) || (storedNights > 0 ? Math.round(storedTotal / storedNights) : 0);
    this.selectedRoom = {
      room_id: room.room_id ?? r.room_id,
      room_number: room.room_number,
      room_type: room.room_type,
      price,
      max_adults: room.max_adults ?? 0,
      max_children: room.max_children ?? 0,
      extra_bed_allowed: !!room.extra_bed_allowed,
      extra_bed_price: room.extra_bed_price ?? 0
    };
    this.suppressDirtyCheck = true;
    this.stayForm.patchValue({
      check_in_date: checkIn,
      check_out_date: checkOut,
      room_id: room.room_id ?? r.room_id ?? null,
      total_amount_override: !!r.total_amount_override,
      total_amount: storedTotal
    });
    this.refreshAutoTotal();
    // A stored total that disagrees with nights x rate was priced by hand —
    // surface it as an override so loading the page never silently rewrites it.
    if (!r.total_amount_override && storedTotal > 0 && storedTotal !== this.computedTotal) {
      this.stayForm.patchValue({
        total_amount_override: true,
        total_amount: storedTotal,
        total_amount_override_reason: r.total_amount_override_reason || 'Carried over from the existing reservation'
      }, { emitEvent: false });
    }
    this.suppressDirtyCheck = false;
    // Self-heal legacy rows where check-out never followed check-in, otherwise
    // the form would be permanently invalid with no way to save.
    this.suppressDirtyCheck = true;
    this.enforceCheckoutAfterCheckin(true);
    this.suppressDirtyCheck = false;
    this.syncRoomSnapshot();
  }
  /**
   * The ledger comes entirely from `get-by-id`'s `payments[]`, which is always
   * present (empty when nothing has been collected). The old `advance_payment`
   * aggregate fallback is gone: it could only ever describe the first advance,
   * so on a reservation with instalments it silently showed one payment instead
   * of all of them.
   */
  private patchPayments(): void {
    this.payments = Array.isArray(this.reservation?.payments) ? this.reservation.payments : [];
    this.refreshPaymentTypes();
  }
  /**
   * The guest master record holds the full profile; the reservation
   * payload only carries a summary. Prefer the master record, fall back
   * to whatever the reservation returned.
   */
  private loadGuest(): void {
    const guestId = this.reservation?.primary_guest?.id;
    if (!guestId) {
      this.patchGuestForm(this.reservation?.primary_guest || {});
      return;
    }
    this._guestService.getGuestById(guestId)
      .subscribe({
        next: (res: any) => {
          this.patchGuestForm(res?.status ? (res.data || {}) : (this.reservation.primary_guest || {}));
        },
        error: () => this.patchGuestForm(this.reservation?.primary_guest || {})
      });
  }
  private patchGuestForm(guest: any): void {
    this.suppressDirtyCheck = true;
    this.guestForm.patchValue({
      first_name: guest.first_name || '',
      last_name: guest.last_name || '',
      gender: guest.gender || '',
      date_of_birth: this.toDate(guest.date_of_birth),
      email: guest.email || '',
      phone_number: guest.phone_number || '',
      address: guest.address || '',
      country_id: guest.country_id ?? '',
      nationality_id: guest.nationality_id ?? '',
      id_type: guest.id_type || '',
      id_number: guest.id_number || '',
      notes: guest.notes || '',
      vip_status: !!guest.vip_status,
      blacklist_status: !!guest.blacklist_status,
      is_active: guest.is_active === undefined ? true : !!guest.is_active
    });
    this.additionalGuests.clear();
    const extras: any[] = guest.additional_guests?.length
      ? guest.additional_guests
      : (this.reservation?.additional_guests || []);
    extras.forEach(g => this.additionalGuests.push(this.createGuest(g)));
    // The enum lists may still be in flight when this runs; whichever response
    // lands last has to do the reconcile.
    this.reconcileEnumValues();
    this.suppressDirtyCheck = false;
    this.syncGuestSnapshot();
    // location cascade: country -> state -> city
    const countryId = guest.country_id;
    if (!countryId) return;
    this.getAllStates(countryId, '', () => {
      this.guestForm.patchValue({ state_id: guest.state_id ?? '' }, { emitEvent: false });
      const stateId = guest.state_id;
      if (!stateId) return;
      this.getAllCities(stateId, '', () => {
        this.guestForm.patchValue({ city_id: guest.city_id ?? '' }, { emitEvent: false });
      });
    });
  }
  // ===============================================================
  //  Status locks
  // ===============================================================
  private applyStatusLocks(): void {
    if (this.isReadOnly) {
      this.stayForm.disable({ emitEvent: false });
      this.guestForm.disable({ emitEvent: false });
      this.paymentForm.disable({ emitEvent: false });
      return;
    }
    if (this.areDatesLocked) {
      ['check_in_date', 'check_out_date'].forEach(k =>
        this.stayForm.get(k)?.disable({ emitEvent: false }));
    }
    if (this.isIdentityLocked) {
      this.identityFields.forEach(k =>
        this.guestForm.get(k)?.disable({ emitEvent: false }));
    }
  }
  // ===============================================================
  //  Availability
  // ===============================================================
  private refreshAutoTotal(): void {
    if (this.stayForm.get('total_amount_override')?.value) return;
    this.stayForm.get('total_amount')?.setValue(this.computedTotal, { emitEvent: false });
  }
  toggleRoomPicker(): void {
    this.showRoomPicker = !this.showRoomPicker;
    if (this.showRoomPicker) this.checkAvailability();
  }
  /**
   * Fetches one page of available rooms for the current stay window.
   * `exclude_reservation_id` (a new contract field) keeps the currently
   * assigned room selectable instead of letting it conflict with itself.
   */
  checkAvailability(page: number = 1): void {
    if (this.areDatesLocked) return;
    const { check_in_date, check_out_date } = this.stayForm.getRawValue();
    if (!check_in_date || !check_out_date) {
      this.availableRooms = [];
      this.availabilityChecked = false;
      this.roomTotalDocs = 0;
      return;
    }
    this.roomPageNumber = page;
    this.isAvailabilityLoading = true;
    this._reservationService.getAvailableRooms({
      page_number: page,
      page_size: this.roomPageSize,
      check_in: this.formatLocalDate(check_in_date),
      check_out: this.formatLocalDate(check_out_date),
      room_type_id: 0,
      // new contract field — keeps the currently assigned room selectable
      exclude_reservation_id: this.reservationId,
      // optional server-side narrowing; the client also filters, so this
      // works even before the backend implements it
      search_value: (this.roomSearchCtrl.value || '').trim()
    })
      .pipe(finalize(() => this.isAvailabilityLoading = false))
      .subscribe({
        next: (res: any) => {
          this.availableRooms = res?.status ? (res.data || []) : [];
          this.roomTotalDocs = res?.meta?.total_records ?? this.availableRooms.length;
          this.availabilityChecked = true;
        },
        error: () => {
          this.availableRooms = [];
          this.availabilityChecked = false;
          this.roomTotalDocs = 0;
        }
      });
  }
  /** search / type filter narrowed on top of the fetched page */
  get filteredRooms(): IAvailableRooms[] {
    const term = (this.roomSearchCtrl.value || '').trim().toLowerCase();
    return this.availableRooms.filter(room => {
      const matchesType = this.roomTypeFilter === 'all' || room.room_type === this.roomTypeFilter;
      if (!matchesType) return false;
      if (!term) return true;
      return String(room.room_number || '').toLowerCase().includes(term)
        || String(room.room_type || '').toLowerCase().includes(term);
    });
  }
  /** room types present in the current result set, for the filter dropdown */
  get roomTypeOptions(): string[] {
    const types = this.availableRooms
      .map(r => r.room_type)
      .filter((t): t is string => !!t);
    return Array.from(new Set(types)).sort();
  }
  get hasActiveRoomFilter(): boolean {
    return this.roomTypeFilter !== 'all' || !!(this.roomSearchCtrl.value || '').trim();
  }
  trackByRoomId(_index: number, room: IAvailableRooms): number | undefined {
    return room.room_id;
  }
  get roomRangeLabel(): string {
    const total = this.roomTotalDocs;
    if (!total) return '';
    const from = (this.roomPageNumber - 1) * this.roomPageSize + 1;
    const to = Math.min(this.roomPageNumber * this.roomPageSize, total);
    return `${from}-${to} of ${total}`;
  }
  onRoomSearch(): void {
    // the search term is sent to the server, so page 1 is where it starts
    this.checkAvailability(1);
  }
  onRoomTypeFilter(): void {
    this.checkAvailability(1);
  }
  onRoomPageChange(e: any): void {
    this.checkAvailability(e.pageIndex + 1);
  }
  clearRoomFilters(): void {
    this.roomSearchCtrl.setValue('');
    this.roomTypeFilterCtrl.setValue('all');
    this.checkAvailability(1);
  }
  selectRoom(room: IAvailableRooms): void {
    this.selectedRoom = room;
    this.stayForm.patchValue({ room_id: room.room_id });
    this.showRoomPicker = false;
    this._snackbar.openSnackBar(`Room ${room.room_number} assigned to this reservation`, 'success');
  }
  isCurrentRoom(room: IAvailableRooms): boolean {
    return this.reservation?.room?.room_id === room.room_id
      || this.reservation?.room_id === room.room_id;
  }
  isAssignedRoom(room: IAvailableRooms): boolean {
    return this.stayForm.get('room_id')?.value === room.room_id;
  }
  // ===============================================================
  //  Save — Stay & Room
  // ===============================================================
  saveRoom(): void {
    this.persistRoom().subscribe();
  }
  private persistRoom(): Observable<boolean> {
    if (this.stayForm.invalid) {
      this.stayForm.markAllAsTouched();
      this._snackbar.openSnackBar('Please fix the highlighted stay details', 'error');
      return of(false);
    }
    if (this.isOverCollected) {
      this._snackbar.openSnackBar(
        `Payments (${this.paidAmount}) already exceed the new total (${this.effectiveTotal}). Record a refund first.`,
        'error'
      );
      return of(false);
    }
    if (this.isOverCapacity) {
      this._snackbar.openSnackBar('Guest count exceeds the capacity of this room', 'error');
      return of(false);
    }
    // NOTE: no availability pre-check here. `get-available-rooms` cannot judge
    // this reservation's own room until the backend honours
    // `exclude_reservation_id` — without it the room always conflicts with its
    // own booking, which is what produced the bogus "Room 201 is not
    // available" error. `PUT /reservation/update` re-validates on the server and
    // returns 400 if the room was genuinely taken, so that is the real gate.
    const v = this.stayForm.getRawValue();
    const payload: IUpdateReservationPayload = {
      reservation_id: this.reservationId,
      room_id: Number(v.room_id),
      check_in_date: this.formatLocalDate(v.check_in_date)!,
      check_out_date: this.formatLocalDate(v.check_out_date)!,
      total_nights: this.totalNights,
      total_amount: Number(this.effectiveTotal),
      // occupancy is owned by the guest section, so it is not sent from here
      total_amount_override: !!v.total_amount_override,
      total_amount_override_reason: v.total_amount_override_reason || '',
      updated_at: this.reservation?.updated_at || null
    };
    this.isSavingRoom = true;
    this.roomState = 'saving';
    return this._reservationService.updateReservation(payload)
      .pipe(
        finalize(() => this.isSavingRoom = false),
        switchMap((res: any) => {
          if (res?.status) {
            this.reservation = {
              ...this.reservation,
              ...payload,
              updated_at: res.data?.updated_at || this.reservation?.updated_at
            };
            // snapshot first — it resets the state to 'idle'
            this.syncRoomSnapshot();
            this.roomState = 'saved';
            this._snackbar.openSnackBar(res.message || 'Stay & room updated', 'success');
            return of(true);
          }
          this.roomState = 'error';
          this._snackbar.openSnackBar(res?.message || 'Failed to update stay & room', 'error');
          return of(false);
        }),
        catchError((err: any) => {
          this.roomState = 'error';
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while updating stay & room', 'error'
          );
          return of(false);
        })
      );
  }
  // ===============================================================
  //  Save — Guest
  // ===============================================================
  saveGuest(): void {
    this.persistGuest().subscribe();
  }
  private persistGuest(): Observable<boolean> {
    if (this.guestForm.invalid) {
      this.guestForm.markAllAsTouched();
      this._snackbar.openSnackBar('Please fix the highlighted guest details', 'error');
      return of(false);
    }
    const formValue = this.guestForm.getRawValue();
    const payload = {
      guest_details: {
        ...formValue,
        id: this.reservation?.primary_guest?.id || 0,
        date_of_birth: formValue.date_of_birth
          ? this.formatLocalDate(formValue.date_of_birth)
          : null,
        additional_guests: formValue.additional_guests || [],
        is_deleted: false
      },
      reservation_id: this.reservationId
    };
    this.isSavingGuest = true;
    this.guestState = 'saving';
    return this._reservationService.updateReservationGuests(payload)
      .pipe(finalize(() => this.isSavingGuest = false))
      .pipe(
        switchMap((res: any) => {
          if (res?.status) {
            // snapshot first — it resets the state to 'idle'
            this.syncGuestSnapshot();
            this.guestState = 'saved';
            this._snackbar.openSnackBar(res.message || 'Guest details updated', 'success');
            return of(true);
          }
          this.guestState = 'error';
          this._snackbar.openSnackBar(res?.message || 'Failed to update guest details', 'error');
          return of(false);
        }),
        catchError((err: any) => {
          this.guestState = 'error';
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while updating guest details', 'error'
          );
          return of(false);
        })
      );
  }
  // ===============================================================
  //  Save — combined (stay & room first, then guest)
  // ===============================================================
  saveAll(): void {
    if (!this.canSaveAll) return;
    this.isSavingAll = true;
    const saveRoom = this.roomDirty;
    const saveGuest = this.guestDirty;
    let chain$: Observable<boolean> = of(true);
    if (saveRoom) chain$ = chain$.pipe(switchMap(() => this.persistRoom()));
    if (saveGuest) {
      chain$ = chain$.pipe(
        switchMap(ok => ok ? this.persistGuest() : of(false))
      );
    }
    chain$
      .pipe(finalize(() => this.isSavingAll = false))
      .subscribe(ok => {
        if (ok) this._snackbar.openSnackBar('All changes for reservation saved successfully.', 'success');
      });
  }
  // ===============================================================
  //  Payments
  // ===============================================================
  togglePaymentForm(): void {
    this.showPaymentForm = !this.showPaymentForm;
    if (this.showPaymentForm && this.currencyList.length === 0) this.getAllCurrencies();
  }
  async addPayment(): Promise<void> {
    if (this.paymentForm.invalid) {
      this.paymentForm.markAllAsTouched();
      return;
    }
    const v = this.paymentForm.getRawValue();
    // Over-collection is legitimate (a guest settling a stay in cash beyond
    // the invoice, a goodwill charge), so it is warned about rather than
    // blocked. The warning covers the payment as a whole -- the entered amount
    // on its own can exceed the total while already-recorded payments sit at
    // zero, and equally the running paid total can cross the total while this
    // single payment is small.
    if (this.wouldOverCollect(Number(v.amount))) {
      const result = await this._confirmService.confirm(
        'Payment exceeds the total',
        this.overCollectMessage(Number(v.amount)),
        'Yes, record it'
      );
      if (!result.isConfirmed) return;
    }
    this.submitPayment(v);
  }
  /**
   * True when adding `amount` pushes the running paid total past the
   * reservation total. A total of 0 means nothing has been priced yet, so there
   * is no ceiling to compare against and nothing to warn about.
   */
  private wouldOverCollect(amount: number): boolean {
    const total = this.effectiveTotal;
    if (total <= 0) return false;
    return this.paidAmount + amount > total;
  }
  private overCollectMessage(amount: number): string {
    const total = this.effectiveTotal;
    const after = this.paidAmount + amount;
    const rupees = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
    const excess = after - total;
    // Nothing paid yet -> the entered amount itself is the problem.
    if (this.paidAmount <= 0) {
      return `This payment is ${rupees(amount)}, which is more than the reservation total of ${rupees(total)}. `
        + `Recording it will make the reservation over-collected by ${rupees(excess)}.`;
    }
    return `Payments already recorded total ${rupees(this.paidAmount)}. Adding ${rupees(amount)} brings them to `
      + `${rupees(after)}, which exceeds the reservation total of ${rupees(total)} by ${rupees(excess)}.`;
  }
  /** the shape `paymentForm.getRawValue()` hands back, derived not restated */
  private submitPayment(v: ReturnType<typeof this.paymentForm.getRawValue>): void {
    // `paid_at` is a DateTime column, so send a full local timestamp rather
    // than a bare date. `verified_by` is deliberately absent — the backend
    // takes it from the auth token. `base_amount` / `exchange_rate` are
    // computed server-side, and `is_deleted` is not a column.
    const payload: IInsertPaymentPayload = {
      reservation_id: this.reservationId,
      payment_type: v.payment_type,
      amount: Number(v.amount),
      currency: v.currency,
      payment_method: v.payment_method,
      payment_status: v.payment_status,
      paid_at: this.formatLocalDateTime(v.paid_at),
      transaction_ref: v.transaction_ref || null,
      remarks: v.remarks || null
    };
    this.isSavingPayment = true;
    this._reservationService.insertPaymentDetails(payload)
      .pipe(finalize(() => this.isSavingPayment = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) {
            this.payments = [
              {
                ...payload,
                id: res.data?.id ?? null,
                // the server echoes the stored row when it can; fall back to
                // what we sent so the ledger paints immediately either way
                base_amount: res.data?.base_amount ?? Number(v.amount),
                paid_at: res.data?.paid_at ?? payload.paid_at
              },
              ...this.payments
            ];
            this.paymentForm.patchValue({
              amount: null,
              transaction_ref: '',
              remarks: '',
              paid_at: new Date()
            });
            this.showPaymentForm = false;
            // the first advance may have just been recorded, which flips the
            // only legal type for the next one
            this.refreshPaymentTypes();
            this._snackbar.openSnackBar(res.message || 'Payment recorded', 'success');
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to record payment', 'error');
          }
        },
        error: (err: any) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while recording payment', 'error'
          );
        }
      });
  }
  signedAmount(payment: IReservationPayment): number {
    const amount = Number(payment.amount) || 0;
    return payment.payment_type === 'refund' ? -amount : amount;
  }
  absAmount(payment: IReservationPayment): number {
    return Math.abs(Number(payment.amount) || 0);
  }
  sectionStateLabel(state: SectionState): string {
    const map: Record<SectionState, string> = {
      idle: 'Unchanged',
      saving: 'Saving',
      saved: 'Saved',
      error: 'Failed'
    };
    return map[state];
  }
  // ===============================================================
  //  Additional guests
  // ===============================================================
  addGuest(): void {
    const last = this.additionalGuests.at(this.additionalGuests.length - 1);
    if (last && last.invalid) {
      last.markAllAsTouched();
      return;
    }
    this.additionalGuests.push(this.createGuest());
  }
  removeGuest(index: number): void {
    this.additionalGuests.removeAt(index);
  }
  private createGuest(g: any = {}): FormGroup {
    return this.fb.group({
      full_name: [g.full_name || '', Validators.required],
      gender: [g.gender || '', Validators.required],
      age: [g.age ?? null, [Validators.required, Validators.min(1)]],
      id_type: [g.id_type || ''],
      id_number: [g.id_number || '']
    });
  }
  // ===============================================================
  //  Lookups
  // ===============================================================
  /**
   * Loads one enum's options into `listProp` and flips `loadingProp` while in
   * flight. Four enums back this page; they differ only by key, so they share
   * one fetch path.
   */
  private fetchEnumOptions(
    enumKey: string,
    listProp: 'genderList' | 'idTypeList' | 'paymentMethodList' | 'paymentStatusList',
    loadingProp: 'isGenderLoading' | 'isIdTypeLoading' | 'isPaymentMethodLoading' | 'isPaymentStatusLoading',
    label: string
  ): void {
    this[loadingProp] = true;
    this._commonService.getEnumOptions(enumKey)
      .pipe(finalize(() => this[loadingProp] = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this[listProp] = res.data || [];
            this.reconcileEnumValues();
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

  private loadEnumOptions(): void {
    this.fetchEnumOptions('gender', 'genderList', 'isGenderLoading', 'genders');
    this.fetchEnumOptions('guests_id_type', 'idTypeList', 'isIdTypeLoading', 'id types');
    this.fetchEnumOptions('payment_method', 'paymentMethodList', 'isPaymentMethodLoading', 'payment methods');
    this.fetchEnumOptions('payment_status', 'paymentStatusList', 'isPaymentStatusLoading', 'payment statuses');
  }

  /**
   * Drops stored enum values the table no longer offers.
   *
   * A guest saved before an option was deactivated still carries that value, and
   * `patchGuestForm` writes it straight into the control. Left alone it renders
   * as a blank select while the control still submits the old key, so the guest
   * screen would silently look empty yet still send the stale value. Clearing
   * instead of substituting a default keeps the visible options and the
   * submitted value the same thing, and lets the existing `required` validator
   * ask for a choice rather than guessing at the guest's identity.
   *
   * The two payment controls are included for the same reason on a smaller
   * scale: they open on `'cash'` / `'success'`, which stop being valid the
   * moment either option is deactivated.
   *
   * Called after each list arrives and again after the guest is patched,
   * because either response can win the race.
   */
  private reconcileEnumValues(): void {
    this.reconcileControl(this.guestForm.get('gender'), this.genderList);
    this.reconcileControl(this.guestForm.get('id_type'), this.idTypeList);
    this.reconcileControl(this.paymentForm.get('payment_method'), this.paymentMethodList);
    this.reconcileControl(this.paymentForm.get('payment_status'), this.paymentStatusList);
    this.additionalGuests.controls.forEach(guest => {
      this.reconcileControl(guest.get('gender'), this.genderList);
      this.reconcileControl(guest.get('id_type'), this.idTypeList);
    });
  }

  private reconcileControl(control: AbstractControl | null, options: IEnumOption[]): void {
    if (!control || !options.length) {
      return;
    }
    const value = control.value;
    if (value && !options.some(option => option.option_key === value)) {
      control.setValue('');
    }
  }

  getAllCountries(searchValue: string = ''): void {
    this.isCountryLoading = true;
    this._commonService.getCountriesList({ search_value: searchValue })
      .pipe(finalize(() => this.isCountryLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) this.countryList = res.data || [];
        },
        error: () => this.countryList = this.countryList
      });
  }
  getAllStates(countryId: number, searchValue: string = '', onDone?: () => void): void {
    if (!countryId) {
      this.stateList = [];
      onDone?.();
      return;
    }
    this.isStateLoading = true;
    this._commonService.getStatesList({ country_id: countryId, search_value: searchValue })
      .pipe(finalize(() => this.isStateLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) this.stateList = res.data || [];
          onDone?.();
        },
        error: () => onDone?.()
      });
  }
  getAllCities(stateId: number, searchValue: string = '', onDone?: () => void): void {
    if (!stateId) {
      this.cityList = [];
      onDone?.();
      return;
    }
    this.isCityLoading = true;
    this._commonService.getCitiesList({ state_id: stateId, search_value: searchValue })
      .pipe(finalize(() => this.isCityLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) this.cityList = res.data || [];
          onDone?.();
        },
        error: () => onDone?.()
      });
  }
  onCountryChange(): void {
    const countryId = Number(this.guestForm.value.country_id) || 0;
    this.stateList = [];
    this.cityList = [];
    this.guestForm.patchValue({ state_id: '', city_id: '' });
    if (countryId) this.getAllStates(countryId);
  }
  onStateChange(): void {
    const stateId = Number(this.guestForm.value.state_id) || 0;
    this.cityList = [];
    this.guestForm.patchValue({ city_id: '' });
    if (stateId) this.getAllCities(stateId);
  }
  getAllCurrencies(searchValue: string = ''): void {
    this.isCurrencyLoading = true;
    this._commonService.getCurrenciesList({ search_value: searchValue })
      .pipe(finalize(() => this.isCurrencyLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) this.currencyList = res.data || [];
        },
        error: () => this.currencyList = this.currencyList
      });
  }
  // ===============================================================
  //  Dirty tracking
  // ===============================================================
  private syncRoomDirty(): void {
    if (this.suppressDirtyCheck) return;
    this.roomDirty = JSON.stringify(this.stayForm.getRawValue()) !== this.roomSnapshot;
    if (this.roomDirty && this.roomState === 'saved') this.roomState = 'idle';
  }
  private syncGuestDirty(): void {
    if (this.suppressDirtyCheck) return;
    this.guestDirty = JSON.stringify(this.guestForm.getRawValue()) !== this.guestSnapshot;
    if (this.guestDirty && this.guestState === 'saved') this.guestState = 'idle';
  }
  private syncRoomSnapshot(): void {
    this.roomSnapshot = JSON.stringify(this.stayForm.getRawValue());
    this.roomDirty = false;
    this.roomState = 'idle';
  }
  private syncGuestSnapshot(): void {
    this.guestSnapshot = JSON.stringify(this.guestForm.getRawValue());
    this.guestDirty = false;
    this.guestState = 'idle';
  }
  /**
   * Nudges check-out forward when check-in lands on or past it. Also used as
   * a self-heal: if the reservation was loaded with an already-invalid window
   * (bad legacy data), the form becomes valid instead of permanently
   * un-saveable.
   */
  // ===============================================================
  //  Cancellation
  // ===============================================================
  /** Mirrors the server's CANCELLABLE_STATUSES */
  private readonly cancellableStatuses = ['created', 'reserved', 'checked_in'];
  isCancelling = false;
  get isCancellable(): boolean {
    return this.cancellableStatuses.includes(this.status);
  }
  onCancel(): void {
    // never leave this page mid-edit and then cancel -- the changes would be
    // silently thrown away along with the booking
    if (this.hasUnsavedChanges) {
      this._confirmService.confirm(
        'Unsaved changes',
        'You have unsaved changes on this reservation. Cancelling will discard them. Continue?',
        'Yes, discard and cancel'
      ).then(ok => { if (ok.isConfirmed) this.promptCancelReason(); });
      return;
    }
    this.promptCancelReason();
  }
  private promptCancelReason(): void {
    const label = this.reservation?.reservation_number || `reservation #${this.reservationId}`;
    this._confirmService
      .confirmWithReason(
        'Cancel reservation',
        `Enter the reason for cancelling ${label}. This is recorded against the booking.`,
        'Yes, cancel reservation',
        'e.g. Guest cancelled by phone'
      )
      .then(({ confirmed, reason }) => { if (confirmed) this.submitCancellation(reason); });
  }
  private submitCancellation(reason: string): void {
    this.isCancelling = true;
    this._reservationService.cancelReservation(this.reservationId, reason)
      .pipe(finalize(() => this.isCancelling = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) {
            this.showPaymentForm = false;
            this.refreshPaymentTypes();
            this.loadReservation();
            this._snackbar.openSnackBar(res.message || 'Reservation cancelled', 'success');
            if (res.data?.refund_required && Number(res.data?.paid_total) > 0) {
              this._snackbar.openSnackBar(
                `A refund of ₹${Number(res.data.paid_total).toLocaleString('en-IN', { maximumFractionDigits: 0 })} is due on this booking.`,
                'warning'
              );
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to cancel reservation', 'error');
          }
        },
        error: (err: any) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while cancelling the reservation', 'error'
          );
        }
      });
  }
  private enforceCheckoutAfterCheckin(silent = false): void {
    const checkIn = this.toDate(this.stayForm.get('check_in_date')?.value);
    const checkOut = this.toDate(this.stayForm.get('check_out_date')?.value);
    if (!checkIn || !checkOut) return;
    const earliest = this.earliestLegalCheckout(checkIn);
    if (checkOut.getTime() >= earliest.getTime()) return;
    this.suppressDirtyCheck = true;
    this.stayForm.patchValue({ check_out_date: earliest }, { emitEvent: false });
    this.suppressDirtyCheck = false;
    this.refreshAutoTotal();
    if (!silent) {
      this._snackbar.openSnackBar(
        `Check-out moved to ${earliest.toDateString()} to keep the stay valid`,
        'success'
      );
    }
  }
  // ===============================================================
  //  Helpers
  // ===============================================================
  private toDate(value: any): Date | null {
    if (!value) return null;
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  private formatLocalDate(date: any): string | null {
    if (!date) return null;
    const d = new Date(date);
    if (isNaN(d.getTime())) return null;
    return [
      d.getFullYear(),
      String(d.getMonth() + 1).padStart(2, '0'),
      String(d.getDate()).padStart(2, '0')
    ].join('-');
  }
  /**
   * Local wall-clock timestamp (`YYYY-MM-DDTHH:mm:ss`). Deliberately not
   * `toISOString()`, which would shift the date across midnight for anyone east
   * or west of UTC.
   */
  private formatLocalDateTime(date: any): string | null {
    if (!date) return null;
    const d = new Date(date);
    if (isNaN(d.getTime())) return null;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${this.formatLocalDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  methodLabel(method?: string): string {
    const map: Record<string, string> = {
      cash: 'Cash',
      card: 'Card',
      upi: 'UPI',
      net_banking: 'Net Banking',
      online: 'Online'
    };
    return map[String(method)] || String(method || 'N/A');
  }
  typeLabel(type?: string): string {
    const map: Record<string, string> = {
      advance: 'Advance',
      additional_advance: 'Additional Advance',
      partial: 'Partial',
      full: 'Full',
      refund: 'Refund'
    };
    return map[String(type)] || String(type || '—');
  }
  statusLabel(status?: string): string {
    const map: Record<string, string> = {
      pending: 'Pending',
      success: 'Success',
      failed: 'Failed',
      refunded: 'Refunded'
    };
    const key = String(status || '');
    return map[key] || key.replace(/_/g, ' ');
  }
  onBack(): void {
    this._router.navigate(['/hms/reservations']);
  }
  onViewDetails(): void {
    this._router.navigate(['hms/reservations', this.reservationId, 'reservation-details']);
  }
  // ===============================================================
  //  Unsaved-changes guard
  // ===============================================================
  canDeactivate(): boolean | Promise<boolean> {
    if (this.isSavingAll || !this.hasUnsavedChanges) return true;
    return this._confirmService
      .confirm('Unsaved changes', 'You have unsaved changes. Leave without saving?', 'Yes, leave')
      .then(result => result.isConfirmed);
  }
}
