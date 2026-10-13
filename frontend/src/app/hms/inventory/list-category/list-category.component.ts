import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { MatTableDataSource } from '@angular/material/table';
import { finalize } from 'rxjs/operators';
import { IGenricGrid, ISearchRequest } from '../../../models/ICommon.model';
import { IInventoryCategory } from '../../../models/IAdmin.model';
import { InventoryService } from '../../../services/inventory.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../../services/confirmation.service';

@Component({
  selector: 'app-list-category',
  templateUrl: './list-category.component.html',
  styleUrl: './list-category.component.scss'
})
export class ListCategoryComponent implements OnInit {
  //// Inject Services
  private _inventoryService = inject(InventoryService);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  /** Base URL for this screen within the active product, for template use. */

  //// Constants
  private readonly STORAGE_KEY = 'hms_invCategoryList';
  //// State Properties
  isPageLoad = false;
  gridSearch = '';
  categoryList: IInventoryCategory[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'name', 'description', 'status', 'actions'];
  dataSource = new MatTableDataSource<IInventoryCategory>();

  //// Request State
  requestData: ISearchRequest = {
    page_number: 1,
    page_size: 10,
    search_value: ''
  } as ISearchRequest;
  ngOnInit(): void {
    this.loadInitialData();
  }

  //// Decides whether to load from localStorage or start fresh
  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
    }
    this.fetchCategoryList();
  }
  //// Core API call method
  private fetchCategoryList(): void {
    this.isPageLoad = true;

    // Sync search value to request object
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));
    this._inventoryService.getCategories(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.categoryList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.categoryList;

            // Recursive check: if current page is empty and we aren't on page 1, go back
            if (this.categoryList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchCategoryList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch categories', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching category list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }
  //// UI Event Handlers
  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchCategoryList();
  }

  applyFilter(): void {
    //// Search if 3+ chars or if input is cleared
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1; // Reset to page 1 on search
      this.fetchCategoryList();
    }
  }
  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.page_number = 1;
    this.fetchCategoryList();
  }

  onEdit(item: IInventoryCategory): void {
    /// Instance-aware prefix: this component is mounted by both products, and a
    /// literal 'hms' made every edit click 404 in the cafe deployment.
    this._router.navigate(['/hms/inventory/update-category', item.id]);
  }
  onDelete(item: IInventoryCategory): void {
    console.log('a', item);
    (document.activeElement as HTMLElement)?.blur();

    this._confirmService.confirm('Do you want to delete this category?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      });
  }
  private executeDelete(item: IInventoryCategory): void {
    this.isPageLoad = true;
    const deletePayload = { ...item, is_active: false, is_deleted: true };

    this._inventoryService.insertUpdateCategory(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Category deleted', 'success');
            this.fetchCategoryList(); // Refresh current view
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting category', 'error');
        }
      });
  }
}
