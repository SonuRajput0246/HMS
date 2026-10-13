import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';

import { UserService } from '../../../services/user.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { IUsers } from '../../../models/IAdmin.model';
import { IGenricGrid, INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';

@Component({
  selector: 'app-list',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss'
})
export class ListComponent implements OnInit {
  // Inject Services
  private _userService = inject(UserService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _confirmService = inject(ConfirmationService);

  // Constants
  private readonly STORAGE_KEY = 'hms_userList';

  // State Properties
  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  usersList: IUsers[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'firstName', 'lastName', 'role', 'email', 'status', 'actions'];
  dataSource = new MatTableDataSource<IUsers>();

  // Request Object with Defaults
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
      { displayValue: 'User Management', isClickable: false, isDashboard: false }
    ];
  }

  /**
   * Initializes data from LocalStorage or defaults
   */
  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
    }
    this.fetchUserList();
  }

  /**
   * Main Data Fetching Logic
   */
  private fetchUserList(): void {
    this.isPageLoad = true;

    // Keep Request and LocalStorage in sync
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));

    this._userService.getUsers(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.usersList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.usersList;

            // Handle empty pages after deletion/filtering
            if (this.usersList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchUserList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch user list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching user list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  // --- Event Handlers ---

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchUserList();
  }

  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1; // Always reset to page 1 on new search
      this.fetchUserList();
    }
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.page_number = 1;
    this.fetchUserList();
  }

  onEdit(item: IUsers): void {
    this._router.navigate(['hms/users/update-user', item.id]);
  }

  onDelete(item: IUsers): void {
    (document.activeElement as HTMLElement)?.blur();
    
    this._confirmService.confirm('Do you want to delete this user?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      });
  }

  private executeDelete(item: IUsers): void {
    this.isPageLoad = true;
    const deletePayload = { ...item, is_active: false, is_deleted: true };

    this._userService.insertUpdateUser(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'User deleted successfully', 'success');
            this.fetchUserList(); // Refresh the current page
          } else {
            this._snackbar.openSnackBar(res.message || 'Failed to delete user', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting user', 'error');
        }
      });
  }
}