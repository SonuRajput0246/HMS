import { Component, inject } from '@angular/core';
import { IEnumOption, IGenricGrid, INavigationaBar } from '../../../models/ICommon.model';
import { ReservationService } from '../../../services/reservation.service';
import { CommonService } from '../../../services/common.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { finalize } from 'rxjs/operators';
import { IFilterReservations, IReservations } from '../../../models/IReservation.model';
import { MatTableDataSource } from '@angular/material/table';
import { ConfirmationService } from '../../../services/confirmation.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-list-reservation',
  templateUrl: './list-reservation.component.html',
  styleUrl: './list-reservation.component.scss'
})
export class ListReservationComponent {
  private _reservationService = inject(ReservationService);
  private _commonService = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _router = inject(Router);
  private readonly STORAGE_KEY = 'hms_reservationList';
  navData: INavigationaBar[] = [];
  isPageLoad = false;
  reservationsList: IReservations[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'reservationNumber', 'roomNumber', 'checkInDate', 'checkOutDate', 'totalNights', 'totalAmount', 'status', 'createdBy', 'createdAt', 'actions'];
  dataSource = new MatTableDataSource<IReservations>();
  /** Status filter options, from the `reservation_status` enum definition. */
  statusList: IEnumOption[] = [];
  isStatusLoading = false;
  requestData: IFilterReservations = {
    page_number: 1,
    page_size: 10,
    from_date: null,
    to_date: null,
    reservation_status: ''
  } as IFilterReservations;

  ngOnInit(): void {
    this.initNavigation();
    this.fetchReservationStatuses();
    this.loadInitialData();
  }

  /**
   * Status filter options from the `reservation_status` enum definition.
   *
   * Was a hardcoded list of four statuses that omitted `created`, the state a
   * new booking opens in, so filtering by the default state was impossible.
   */
  private fetchReservationStatuses(): void {
    this.isStatusLoading = true;
    this._commonService.getEnumOptions('reservation_status')
      .pipe(finalize(() => this.isStatusLoading = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) {
            this.statusList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch reservation statuses', 'error');
          }
        },
        error: (err: any) => {
          const msg = err?.error?.message || 'An error occurred while fetching reservation statuses';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: false, isDashboard: false },
      { displayValue: 'Reservations', isClickable: false, isDashboard: false }
    ];
  }
  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
    }
    this.fetchAllReservations();
  }

  private formatLocalDate(date: any): string | null {
    if (!date) return null;
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private fetchAllReservations(): void {
    this.isPageLoad = true;
    const payload = {
      ...this.requestData,
      from_date: this.formatLocalDate(this.requestData.from_date),
      to_date: this.formatLocalDate(this.requestData.to_date)
    }
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));
    this._reservationService.getAllReservations(payload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.reservationsList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.reservationsList;
            if (this.reservationsList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchAllReservations();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch reservation list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching reservation list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }
  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchAllReservations();
  }

  applyFilter(): void {
    this.requestData.page_number = 1;
    this.fetchAllReservations();
  }
  clearFilter(): void {
    this.requestData.from_date = null;
    this.requestData.to_date = null;
    this.requestData.search_room_number_value = '';
    this.requestData.reservation_status = '';
    this.requestData.page_number = 1;
    this.fetchAllReservations();
  }

  onView(item: IReservations): void {
    this._router.navigate(['hms/reservations', item.reservation_id, 'reservation-details']);
  }

  onEdit(item: IReservations): void {
    if (item.reservation_id !== undefined) {
      this._router.navigate(['hms/reservations/edit', item.reservation_id]);
    }
  }
  onDelete(item: IReservations): void {
    (document.activeElement as HTMLButtonElement)?.blur();
    this._confirmService.confirm('Do you want to delete this reservation?')
      .then((result) => {
        if (result.isConfirmed) {
          if (item.reservation_id !== undefined) {
            this.executeDelete(item.reservation_id);
          }
        }
      });
  }
  private executeDelete(reservationId: number): void {
    this.isPageLoad = true;
    this._reservationService.deleteReservation(reservationId)
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Reservation deleted successfully', 'success');
            this.reservationsList = this.reservationsList.filter(item => item.reservation_id !== reservationId);
            this.dataSource.data = this.reservationsList;
            this.fetchAllReservations();
          } else {
            this.isPageLoad = false;
            this._snackbar.openSnackBar(res?.message || 'Failed to delete reservation', 'error');
          }
        },
        error: (err) => {
          this.isPageLoad = false;
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting reservation', 'error');
        }
      })
  }
}
