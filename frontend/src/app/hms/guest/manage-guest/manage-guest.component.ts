import { Component, inject } from '@angular/core';
import { FormBuilder, FormControl, FormGroup, Validators } from '@angular/forms';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ActivatedRoute, Router } from '@angular/router';
import { INavigationaBar, IEnumOption } from '../../../models/ICommon.model';
import { GuestService } from '../../../services/guest.service';
import { debounceTime, distinctUntilChanged, finalize } from 'rxjs/operators';
import { CommonService } from '../../../services/common.service';
@Component({
  selector: 'app-manage-guest',
  templateUrl: './manage-guest.component.html',
  styleUrl: './manage-guest.component.scss'
})
export class ManageGuestComponent {
  private fb = inject(FormBuilder);
  private _guestService = inject(GuestService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);
  private _commonService = inject(CommonService);
  navData: INavigationaBar[] = [];
  guestForm!: FormGroup;
  breakpoint = 3;
  isLoading = false;
  isPageLoad = false;
  isCountryLoading = false;
  isStateLoading = false;
  isCityLoading = false;
  isIdTypeLoading = false;
  isGenderLoading = false;
  /** Sourced from the `guests_id_type` / `gender` enum definitions. */
  idTypeList: IEnumOption[] = [];
  genderList: IEnumOption[] = [];
  guestObj: any = { id: 0 };
  isEditMode = false;
  readonly startDate = new Date(2000, 0, 1);
  countryList: any[] = [];
  stateList: any[] = [];
  cityList: any[] = [];
  nationalityList: any[] = [];
  countrySearchCtrl = new FormControl('');
  stateSearchCtrl = new FormControl('');
  citySearchCtrl = new FormControl('');
  selectedCountryId: number | null = null;
  selectedStateId: number | null = null;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.onResize();
    this.getAllCountries();
    this.getEnumOptions('guests_id_type', 'idTypeList', 'isIdTypeLoading', 'id types');
    this.getEnumOptions('gender', 'genderList', 'isGenderLoading', 'genders');
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
    const guestId = Number(this.AR.snapshot.paramMap.get('id'));
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
        { displayValue: 'Add Guest', isClickable: false, isDashboard: false }
      ];
    }
  }

  initNavigation() {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Guest Management', isClickable: true, isDashboard: false, redirectValue: '/hms/guests' }
    ]
  }
  onResize() {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }
  createForm() {
    this.guestForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      gender: ['', Validators.required],
      date_of_birth: ['', Validators.required],
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
      is_active: [true]
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
                is_active: this.guestObj.is_active
              });
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
          error: (err) => {
            const msg = err.error?.message || 'A error occured while fetching guest';
            this._snackbar.openSnackBar(msg, 'error');
          }
        })
    }
  }
  insertUpdateGuest(): void {
    if (this.guestForm.invalid) {
      this.guestForm.markAllAsTouched();
      return;
    }
    const payload = {
      ...this.guestForm.value,
      id: this.guestObj?.id || 0,
      date_of_birth: this.guestForm.value.date_of_birth
        ? this.guestForm.value.date_of_birth.toISOString().split('T')[0]
        : null,
      is_deleted: false
    };
    this.isLoading = true;
    this._guestService.insertUpdateGuest(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Guest saved successfully', 'success')
            this._router.navigate(['hms/guests'])
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save guest', 'error')
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving guest';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  /**
   * Load one enum definition's options into a component field.
   *
   * Generic on purpose: the same call serves id_type, gender, and any other
   * enum-backed dropdown, so the option list lives only in the database.
   */
  getEnumOptions(
    enumKey: string,
    target: 'idTypeList' | 'genderList',
    loadingFlag: 'isIdTypeLoading' | 'isGenderLoading',
    friendlyName: string
  ): void {
    this[loadingFlag] = true;
    this._commonService.getEnumOptions(enumKey)
      .pipe(finalize(() => this[loadingFlag] = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this[target] = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || `Failed to fetch ${friendlyName}`, 'error');
          }
        },
        error: (err) => {
          const msg = err?.error?.message || `An error occurred while fetching ${friendlyName}`;
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
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
}
