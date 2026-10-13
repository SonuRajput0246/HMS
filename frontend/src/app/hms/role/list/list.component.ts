import { Component, inject, ViewChild } from '@angular/core';
import { RoleManagementService } from '../../../services/role-management.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { Router } from '@angular/router';
import { ConfirmationService } from '../../../services/confirmation.service';
import { IGenricGrid, INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';
import { IRoles } from '../../../models/IAdmin.model';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-list',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss'
})
export class ListComponent {

  private _roleService = inject(RoleManagementService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _confirmService = inject(ConfirmationService);

  private readonly STORAGE_KEY = 'hms_roleList';

  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  roleList: IRoles[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'roleCode', 'roleName', 'status', 'actions'];
  dataSource = new MatTableDataSource<IRoles>();

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
      { displayValue: 'Role Management', isClickable: false, isDashboard: false }
    ];
  }

  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
    }
    this.fetchRoleList();
  }

  private fetchRoleList(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));

    this._roleService.GetRoles(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roleList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.roleList;

            if (this.roleList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchRoleList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch role list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching role list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchRoleList();
  }

  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchRoleList();
    }
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.page_number = 1;
    this.fetchRoleList();
  }

  onEdit(item: IRoles): void {
    this._router.navigate(['hms/roles/update-role', item.id]);
  }

  OnEditRoleAccess(item: IRoles) {
    this._router.navigate(['hms/roles/manage-role-access/' + item.id]);
  }

  onDelete(item: IRoles): void {
    (document.activeElement as HTMLElement)?.blur();
    this._confirmService.confirm('Do you want to delete this role?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      });
  }

  private executeDelete(item: IRoles): void {
    this.isPageLoad = true;
    const deletePayload = { ...item, is_active: false, is_deleted: true };

    this._roleService.insertUpdateRole(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Role deleted successfully', 'success');
            this.fetchRoleList();
          } else {
            this._snackbar.openSnackBar(res.message || 'Failed to delete role', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting role', 'error');
        }
      })
  }


}
