import { Component, inject } from '@angular/core';
import { ReservationService } from '../../../services/reservation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IGenricGrid, INavigationaBar } from '../../../models/ICommon.model';
import { IAvailableRooms, IDraftReservationData, IFilterAvailableRooms, IRoomType } from '../../../models/IReservation.model';
import { MatTableDataSource } from '@angular/material/table';
import { finalize } from 'rxjs/operators';
import { RoomService } from '../../../services/room.service';
import { Router } from '@angular/router';
import { BookingStateService } from '../../../services/booking-state.service';

@Component({
  selector: 'app-available-room',
  templateUrl: './available-room.component.html',
  styleUrl: './available-room.component.scss'
})
export class AvailableRoomComponent {

  private _reservationService = inject(ReservationService);
  private _roomService = inject(RoomService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router)
  private _bookingStateService = inject(BookingStateService);

  private readonly STORAGE_KEY = 'hms_availableRoomList';

  navData: INavigationaBar[] = [];
  isPageLoad = false;
  today = new Date();
  availableRoomsList: IAvailableRooms[] = [];
  roomTypesList: IRoomType[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'roomNumber', 'roomType', 'price', 'maxAdults', 'maxChildren', 'maxInfants', 'extraBedAllowed', 'extraBedPrice', 'roomAmenities', 'actions'];
  dataSource = new MatTableDataSource<IAvailableRooms>();

  requestData: IFilterAvailableRooms = {
    page_number: 1,
    page_size: 10,
    check_in: null,
    check_out: null,
    room_type_id: 0
  } as IFilterAvailableRooms;

  ngOnInit(): void {
    this.initNavigation();
    this.loadInitialData();
    this.fetchRoomTypes();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Available Rooms', isClickable: false, isDashboard: false }
    ];
  }

  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
    }
    this.fetchAllAvailableRooms();
  }

  private formatLocalDate(date: any): string | null {
    if (!date) return null;
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private fetchAllAvailableRooms(): void {
    this.isPageLoad = true;

    const payload = {
      ...this.requestData,
      check_in: this.formatLocalDate(this.requestData.check_in),
      check_out: this.formatLocalDate(this.requestData.check_out)
    }
    
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));

    this._reservationService.getAvailableRooms(payload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.availableRoomsList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.availableRoomsList;

            if (this.availableRoomsList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchAllAvailableRooms();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch available rooms list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching available rooms list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchAllAvailableRooms();
  }

  applyFilter(): void {
    this.requestData.page_number = 1;
    this.fetchAllAvailableRooms();
  }

  clearFilter(): void {
    this.requestData.check_in = null;
    this.requestData.check_out = null;
    this.requestData.room_type_id = 0;
    this.requestData.page_number = 1;
    this.fetchAllAvailableRooms();
  }

  fetchRoomTypes() {
    this._roomService.getRoomTypes()
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roomTypesList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch available rooms types', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching available rooms types';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  bookRoom(item: IAvailableRooms): void {
    if (!this.requestData.check_in || !this.requestData.check_out) {
      this._snackbar.openSnackBar('Please select check-in and check-out dates', 'error');
      return;
    }

    const checkInStr = this.formatLocalDate(this.requestData.check_in)!;
    const checkOutStr = this.formatLocalDate(this.requestData.check_out)!;

    //// Calculate total nights
    const checkIn = new Date(checkInStr);
    const checkOut = new Date(checkOutStr);
    const nights = Math.ceil((checkOut.getTime() - checkIn.getTime()) / (1000 * 3600 * 24)) || 1;
  
    const draftReservationData: IDraftReservationData = {
      reservation_id: 0,
      room_id: item.room_id,
      room_number: item.room_number,
      room_type: item.room_type,
      price_per_night: item.price,
      total_amount: (item.price ?? 0) * nights,
      check_in_date: checkInStr,
      check_out_date: checkOutStr,
      total_nights: nights
    };

    //// 1. Save full payload to state service
    this._bookingStateService.setRoomSelection(draftReservationData);

    //// 2. Navigate to guest selection
    this._router.navigate(['hms/reservations/select-guest']);
  }

getAmenityIcon(name: unknown): string {
  const key = String(name);

  const map: any = {
    'Air Conditioning': 'ac_unit',
    'Television': 'tv',
    'High-Speed Wi-Fi': 'wifi',
    'Work Desk': 'desk',
    'Wardrobe': 'checkroom'
  };

  return map[key] || 'check_circle';
}


}
