import { Component, inject, ViewChild } from '@angular/core';
import { GuestService } from '../../../services/guest.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { ConfirmationService } from '../../../services/confirmation.service';
import { IGenricGrid, INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';
import { IGuest } from '../../../models/IGuest.model';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs';

@Component({
  selector: 'app-list',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss'
})
export class ListComponent {

  private _guestService = inject(GuestService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _confirmService = inject(ConfirmationService);

  private readonly STORAGE_KEY = 'hms_guestList';

  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  guestList: IGuest[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'guestName', 'gender', 'email', 'phoneNumber', 'nationality', 'notes', 'vipStatus', 'status', 'actions'];
  dataSource = new MatTableDataSource<IGuest>();

  requestData: ISearchRequest = {
    page_number: 1,
    page_size: 10,
    search_value: ''
  } as ISearchRequest;
  
  @ViewChild(MatPaginator) paginator!: MatPaginator;

  ngOnInit(): void {
    this.initNavigation();
    this.loadInitialData();
  }


  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Guest Management', isClickable: false, isDashboard: false }
    ]
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

  onEdit(item: IGuest): void {
    this._router.navigate(['hms/guests/update-guest', item.id]);
  }

  onDelete(item: IGuest): void {
    (document.activeElement as HTMLButtonElement)?.blur();
    this._confirmService.confirm('Do you want to delete this guest?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      });
  }

  private executeDelete(item: IGuest): void {
    if (!item.id) {
      this._snackbar.openSnackBar('Unable to delete guest: missing guest id', 'error');
      return;
    }
    this.isPageLoad = true;
    // Send only the flags needed for the soft delete. Spreading the whole row would
    // re-write every column with values from the list response, which is lossy
    // (e.g. it returns `nationality` as a name, not `nationality_id`).
    const deletePayload = { id: item.id, is_active: false, is_deleted: true };

    this._guestService.insertUpdateGuest(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Guest deleted successfully', 'success');
            this.fetchGuestList();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete guest', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting guest', 'error');
        }
      })
  }



}
