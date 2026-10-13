import { Component, inject, ViewChild } from '@angular/core';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { IGenricGrid, INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';
import { IGuest } from '../../../models/IGuest.model';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs';
import { GuestService } from '../../../services/guest.service';
import { BookingStateService } from '../../../services/booking-state.service';
@Component({
  selector: 'app-select-guest',
  templateUrl: './select-guest.component.html',
  styleUrl: './select-guest.component.scss'
})
export class SelectGuestComponent {
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _guestService = inject(GuestService);
  private _bookingStateService = inject(BookingStateService);
  private readonly STORAGE_KEY = 'hms_guestList';
  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  guestList: IGuest[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'guestName', 'gender', 'email', 'phoneNumber', 'nationality', 'notes', 'vipStatus', 'status', 'actions'];
  dataSource = new MatTableDataSource<IGuest>();
  draftReservation = this._bookingStateService.draftBooking;
  requestData: ISearchRequest = {
    page_number: 1,
    page_size: 10,
    search_value: ''
  } as ISearchRequest;
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  ngOnInit(): void {
    this.initNavigation();
    this.verifyDraftReservation();
    this.loadInitialData();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Select or Create Guest', isClickable: false, isDashboard: false, redirectValue: '/hms/guest-details' }
    ]
  }
  private verifyDraftReservation(): void {
    if (!this.draftReservation) {
      this._snackbar.openSnackBar('No draft booking found. Please select a room first.', 'error');
      this._router.navigate(['hms/reservations/available-rooms']);
    }
  }
  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
    }
    this.fetchGuestList();
  }
  private fetchGuestList(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));
    this._guestService.getGuests(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.guestList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.guestList;
            if (this.guestList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchGuestList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch guest list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching guest list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  onSelectGuest(guest: IGuest): void {
    if (guest.id === undefined) {
      this._snackbar.openSnackBar('Selected guest has an invalid ID.', 'error');
      return;
    }
    this._bookingStateService.updateGuestInfo(guest.id, guest.first_name + ' ' + guest.last_name);
    this._router.navigate(['hms/reservations/guest-details', guest.id]);
  }
  // Call this when staff clicks "Create New Guest" button
  onCreateNewGuest(): void {
    // // Preserve draft state in sessionStorage before route transition
    if (!this.draftReservation) {
      this._snackbar.openSnackBar('Draft booking session expired. Please restart booking.', 'error');
      this._router.navigate(['hms/reservations/available-rooms']);
      return;
    }
    this._router.navigate(['hms/guests/create']);
  }
  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchGuestList();
  }
  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchGuestList();
    }
  }
  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.page_number = 1;
    this.fetchGuestList();
  }

}
