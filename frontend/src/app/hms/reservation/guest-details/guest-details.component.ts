import { Component, inject } from '@angular/core';
import { AbstractControl, FormArray, FormBuilder, FormControl, FormGroup, Validators } from '@angular/forms';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ActivatedRoute, Router } from '@angular/router';
import { IEnumOption, INavigationaBar } from '../../../models/ICommon.model';
import { debounceTime, distinctUntilChanged, finalize } from 'rxjs/operators';
import { CommonService } from '../../../services/common.service';
import { ReservationService } from '../../../services/reservation.service';
import { GuestService } from '../../../services/guest.service';
import { minAgeValidator } from '../../../validators/minAgeValidator';
import { BookingStateService } from '../../../services/booking-state.service';
@Component({
  selector: 'app-guest-details',
  templateUrl: './guest-details.component.html',
  styleUrl: './guest-details.component.scss'
})
export class GuestDetailsComponent {
  private fb = inject(FormBuilder);
  private _reservationService = inject(ReservationService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);
  private _commonService = inject(CommonService);
  private _guestService = inject(GuestService);
  private _bookingStateService = inject(BookingStateService);
  private readonly DRAFT_RESERVATION_KEY = 'hms_draft_reservation';
  draftReservation = this._bookingStateService.draftBooking;
  navData: INavigationaBar[] = [];
  guestForm!: FormGroup;
  breakpoint = 3;
  isLoading = false;
  isPageLoad = false;
  isCountryLoading = false;
  isStateLoading = false;
  isCityLoading = false;
  /**
   * Enum-backed dropdowns, read from the `enum_definitions` / `enum_options`
   * tables so an option added in the admin UI appears here without a frontend
   * change. `option_key` is the exact string stored on the column.
   *
   * Shared by the primary guest and every companion in `additionalGuests`.
   */
  genderList: IEnumOption[] = [];
  idTypeList: IEnumOption[] = [];
  isGenderLoading = false;
  isIdTypeLoading = false;
  guestObj: any = { id: 0 };
  isEditMode = false;
  readonly startDate = new Date(2000, 0, 1);
  maxDate: Date = new Date(new Date().setFullYear(new Date().getFullYear() - 18));
  countryList: any[] = [];
  stateList: any[] = [];
  cityList: any[] = [];
  countrySearchCtrl = new FormControl('');
  stateSearchCtrl = new FormControl('');
  citySearchCtrl = new FormControl('');
  selectedCountryId: number | null = null;
  selectedStateId: number | null = null;

  ngOnInit(): void {
    this.createForm();
    this.onResize();
    this.getAllCountries();
    this.loadEnumOptions();
    this.verifyDraftReservation();
    this.countrySearchCtrl.valueChanges
      .pipe(
        debounceTime(400),
        distinctUntilChanged()
      )
      .subscribe(search => {
        this.getAllCountries(search || '');
      });

      this.guestForm.get('country_id')?.valueChanges.subscribe(countryId => {
        const stateControl = this.guestForm.get('state_id');
        this.selectedCountryId = countryId;
        stateControl?.reset();
        this.stateList = [];
        if (countryId) {
          stateControl?.enable();     // ✅ enable state dropdown
          this.getAllStates(countryId);
        } else {
          stateControl?.disable();    // ✅ disable again
        }
      });
    this.stateSearchCtrl.valueChanges
      .pipe(
        debounceTime(400),
        distinctUntilChanged()
      )
      .subscribe(search => {
        if (this.selectedCountryId) {
          this.getAllStates(this.selectedCountryId, search || '');
        }
      });
    this.guestForm.get('state_id')?.valueChanges.subscribe(stateId => {
      const cityControl = this.guestForm.get('city_id');
      this.selectedStateId = stateId;
      cityControl?.reset();
      this.cityList = [];
      if (stateId) {
        cityControl?.enable();
        this.getAllCities(stateId);
      } else {
        cityControl?.disable();
      }
    });

    this.citySearchCtrl.valueChanges
      .pipe(
        debounceTime(400),
        distinctUntilChanged()
      )
      .subscribe(search => {
        if (this.selectedStateId) {
          this.getAllCities(this.selectedStateId, search || '');
        }
      });
    this.initNavigation();
    const guestId = Number(this.AR.snapshot.paramMap.get('guestId'));
    if (guestId) {
      this.isEditMode = true;
      this.getGuestById(guestId);
      this.navData = [
        ...this.navData,
        { displayValue: 'Edit Guest', isClickable: false, isDashboard: false }
      ];
    } else {
      this.navData = [
        ...this.navData,
        { displayValue: 'Add New Guest', isClickable: false, isDashboard: false }
      ];
    }

  }

  initNavigation() {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Select or Create Guest', isClickable: true, isDashboard: false, redirectValue: `/hms/reservations/select-guest` },
    ]
  }
  private verifyDraftReservation(): void {
    if (!this.draftReservation()) {
      this._snackbar.openSnackBar('No draft booking found. Please select a room first.', 'error');
      this._router.navigate(['hms/reservations/available-rooms']);
    }
  }
  onResize() {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }
  createForm() {
    this.guestForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      gender: ['', Validators.required],
      date_of_birth: ['', [Validators.required, minAgeValidator(18)]],
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
  }
  private getGuestById(guestId: number): void {
    if (guestId > 0) {
      this.isPageLoad = true;
      this._guestService.getGuestById(guestId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.isEditMode = true;
              this.guestObj = res.data;
              this.guestForm.patchValue({
                first_name: this.guestObj.first_name,
                last_name: this.guestObj.last_name,
                gender: this.guestObj.gender,
                date_of_birth: this.guestObj.date_of_birth 
                  ? new Date(this.guestObj.date_of_birth) 
                  : null,
                email: this.guestObj.email,
                phone_number: this.guestObj.phone_number,
                address: this.guestObj.address,
                country_id: this.guestObj.country_id,
                nationality_id: this.guestObj.nationality_id,
                id_type: this.guestObj.id_type,
                id_number: this.guestObj.id_number,
                notes: this.guestObj.notes,
                vip_status: this.guestObj.vip_status,
                blacklist_status: this.guestObj.blacklist_status,
                is_active: this.guestObj.is_active,
              });
              this.additionalGuests.clear();
              if (this.guestObj.additional_guests?.length) {
                this.guestObj.additional_guests.forEach((g: any) => {
                  // Built by `createGuest` so this path and `addGuest` produce
                  // the same controls. The group was previously built inline with
                  // only full_name/gender/age, so the template's Id Type and Id
                  // Number bindings had no control behind them in edit mode.
                  const companion = this.createGuest();
                  companion.patchValue({
                    full_name: g.full_name ?? '',
                    gender: g.gender ?? '',
                    age: g.age ?? '',
                    id_type: g.id_type ?? '',
                    id_number: g.id_number ?? ''
                  });
                  this.additionalGuests.push(companion);
                });
              } else {
                this.addGuest();
              }
              // The enum lists may still be in flight when this runs; whichever
              // response lands last has to do the reconcile.
              this.reconcileEnumValues();
              this.getAllStates(this.guestObj.country_id);
              this._commonService.getStatesList({ country_id: this.guestObj.country_id })
                .subscribe(res => {
                  this.stateList = res.data;
                  this.guestForm.patchValue({ state_id: this.guestObj.state_id });
                  this._commonService.getCitiesList({ state_id: this.guestObj.state_id })
                    .subscribe(cityRes => {
                      this.cityList = cityRes.data;
                      this.guestForm.patchValue({ city_id: this.guestObj.city_id });
                    });
                });
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to fetch guest', 'error');
            }
          },
          error: (err: any) => {
            const msg = err.error?.message || 'A error occured while fetching guest';
            this._snackbar.openSnackBar(msg, 'error');
          }
        })
    }
  }

  insertGuestAndReservation(): void {
    if (this.guestForm.invalid) {
      this.guestForm.markAllAsTouched();
      return;
    }
    const draft = this.draftReservation();
    if (!draft) {
      this._snackbar.openSnackBar('Draft booking session expired. Please restart booking.', 'error');
      this._router.navigate(['hms/reservations/available-rooms']);
      return;
    }
    let formValue = this.guestForm.getRawValue();
    const payload = {
      guest_details: {
        ...formValue,
        id: this.guestObj?.id || 0,
        date_of_birth: this.guestForm.value.date_of_birth
          ? this.guestForm.value.date_of_birth.toISOString().split('T')[0]
          : null,
        additional_guests: formValue.additional_guests || [],
        is_deleted: false
      },
      reservation_details: {
        reservation_id: draft.reservation_id,
        room_id: draft.room_id,
        check_in_date: draft.check_in_date,
        check_out_date: draft.check_out_date
      }
    };
    this.isLoading = true;
    this._reservationService.insertGuestAndReservation(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            const reservationId = res.data?.reservation_id;
            this._snackbar.openSnackBar(res?.message || 'Reservation created successfully', 'success');
            this._router.navigate(['hms/reservations', reservationId, 'advance-payment'])
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save reservation', 'error')
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving reservation';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  getAllCountries(searchValue: string = ''): void {
    this.isCountryLoading = true;
    this._commonService.getCountriesList({"search_value": searchValue})
      .pipe(finalize(() => this.isCountryLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.countryList = res?.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch countries', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while fetching countries';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  getAllStates(countryId: number, searchValue: string = ''): void {
    this.isStateLoading = true;
    this._commonService.getStatesList({
        country_id: countryId,
        search_value: searchValue
      })
      .pipe(finalize(() => this.isStateLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.stateList = res?.data || [];
          } else {
            this._snackbar.openSnackBar(
              res?.message || 'Failed to fetch states',
              'error'
            );
          }
        },
        error: (err) => {
          const msg = err?.error?.message || 'An error occurred while fetching states';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  getAllCities(stateId: number, searchValue: string = ''): void {
    this.isCityLoading = true;
    this._commonService.getCitiesList({
        state_id: stateId,
        search_value: searchValue
      })
      .pipe(finalize(() => this.isCityLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.cityList = res?.data || [];
          } else {
            this._snackbar.openSnackBar(
              res?.message || 'Failed to fetch cities',
              'error'
            );
          }
        },
        error: (err) => {
          const msg = err?.error?.message || 'An error occurred while fetching cities';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  /**
   * Loads one enum's options into `listProp` and flips `loadingProp` while in
   * flight. The two enums differ only by key, so they share one fetch path.
   */
  private fetchEnumOptions(
    enumKey: string,
    listProp: 'genderList' | 'idTypeList',
    loadingProp: 'isGenderLoading' | 'isIdTypeLoading',
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
  }

  /** True while either enum-backed dropdown is still populating. */
  get isEnumLoading(): boolean {
    return this.isGenderLoading || this.isIdTypeLoading;
  }

  /**
   * Drops stored enum values the table no longer offers.
   *
   * A guest saved before an option was deactivated still carries that value, and
   * `getGuestById` writes it straight into the control. Left alone it renders as
   * a blank select while the control still submits the old key, so the screen
   * would look empty and still send the stale value. Clearing rather than
   * substituting a default keeps the visible options and the submitted value the
   * same thing, and lets the existing `required` validator ask for a choice
   * instead of guessing at the guest's identity.
   *
   * Called after each list arrives and again after the guest is patched, because
   * either response can win the race.
   */
  private reconcileEnumValues(): void {
    this.reconcileControl(this.guestForm.get('gender'), this.genderList);
    this.reconcileControl(this.guestForm.get('id_type'), this.idTypeList);
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

  get additionalGuests(): FormArray {
    return this.guestForm.get('additional_guests') as FormArray;
  }
  addGuest() {
    const lastGuest = this.additionalGuests.at(this.additionalGuests.length - 1);
    if (lastGuest && lastGuest.invalid) {
      lastGuest.markAllAsTouched();
      return;
    }
    this.additionalGuests.push(this.createGuest());
  }
  removeGuest(index:number){
    this.additionalGuests.removeAt(index);
  }
  private createGuest(): FormGroup {
    return this.fb.group({
      full_name: ['', Validators.required],
      gender: ['', Validators.required],
      age: ['', [Validators.required, Validators.min(1)]],
      id_type: [''],
      id_number: ['']
    });
  }
}
