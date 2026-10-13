import { Component, inject } from '@angular/core';
import { RoomService } from '../../../services/room.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IGenricGrid, INavigationaBar } from '../../../models/ICommon.model';
import { IFilterRooms, IRooms } from '../../../models/IRoom.model';
import { MatTableDataSource } from '@angular/material/table';
import { finalize } from 'rxjs/operators';
import { IRoomType } from '../../../models/IReservation.model';
import { ConfirmationService } from '../../../services/confirmation.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-list-room',
  templateUrl: './list-room.component.html',
  styleUrl: './list-room.component.scss'
})
export class ListRoomComponent {

  private _roomService = inject(RoomService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService)
  private _router = inject(Router);

  private readonly STORAGE_KEY = 'hms_roomList';

  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  roomsList: IRooms[] = [];
  roomTypesList: IRoomType[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'roomNumber', 'roomType', 'room_status', 'view', 'notes', 'actions'];
  dataSource = new MatTableDataSource<IRooms>();

  requestData: IFilterRooms = {
    page_number: 1,
    page_size: 10,
    room_type_id: 0
  } as IFilterRooms;

  ngOnInit(): void {
    this.initNavigation();
    this.loadInitialData();
    this.fetchRoomTypes();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Room Management', isClickable: false, isDashboard: false },
      { displayValue: 'Rooms', isClickable: false, isDashboard: false }
    ];
  }

  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
    }
    this.fetchRoomList();
  }

  private fetchRoomList(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));
    this._roomService.getAllRooms(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roomsList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.roomsList;

            if (this.roomsList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchRoomList();
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
    this.fetchRoomList();
  }

  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchRoomList();
    }
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.room_type_id = 0;
    this.requestData.page_number = 1;
    this.fetchRoomList();
  }

  onEdit(item: IRooms): void {
    this._router.navigate(['hms/rooms/update-room', item.id]);
  }

  onDelete(item: IRooms): void {
    (document.activeElement as HTMLElement)?.blur();

    this._confirmService.confirm('Do you want to delete this room?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      })
  }

  private executeDelete(item: IRooms): void {
    this.isPageLoad = true;
    const deletePayload = { ...item, is_active: false, is_deleted: true };
    this._roomService.insertUpdateRoom(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Room deleted successfully', 'success');
            this.fetchRoomList();
          } else {
            this._snackbar.openSnackBar(res.message || 'Failed to delete room', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting user', 'error');
        }
      });
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

}
