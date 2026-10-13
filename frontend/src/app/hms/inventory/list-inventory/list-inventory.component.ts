import { Component, inject } from '@angular/core';
import { InventoryService } from '../../../services/inventory.service';
import { Router } from '@angular/router';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { IInventory } from '../../../models/IAdmin.model';
import { IGenricGrid, ISearchRequest } from '../../../models/ICommon.model';
import { finalize } from 'rxjs/operators';
import { MatTableDataSource } from '@angular/material/table';

@Component({
  selector: 'app-list-inventory',
  templateUrl: './list-inventory.component.html',
  styleUrl: './list-inventory.component.scss'
})
export class ListInventoryComponent {
  //// Inject Services
  private _inventoryService = inject(InventoryService);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);

  //// Constants
  private readonly STORAGE_KEY = 'hms_inventoryList';

  //// State Properties
  isPageLoad = false;
  gridSearch = '';
  inventoryList: IInventory[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'name', 'category_name', 'quantity', 'unit', 'unit_cost', 'status', 'actions'];
  dataSource = new MatTableDataSource<IInventory>();

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
    this.fetchInventoryList();
  }

  //// Core API call method
  private fetchInventoryList(): void {
    this.isPageLoad = true;
    
    // Sync search value to request object
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));

    this._inventoryService.getInventories(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.inventoryList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.inventoryList;

            // Recursive check: if current page is empty and we aren't on page 1, go back
            if (this.inventoryList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchInventoryList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch inventory items', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching inventory items';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  //// UI Event Handlers
  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchInventoryList();
  }

  applyFilter(): void {
    //// Search if 3+ chars or if input is cleared
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1; // Reset to page 1 on search
      this.fetchInventoryList();
    }
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.requestData.page_number = 1;
    this.fetchInventoryList();
  }

  onEdit(item: IInventory): void {
    this._router.navigate(['/hms/inventory/update-inventory', item.id]);
  }

  onDelete(item: IInventory): void {
    (document.activeElement as HTMLElement)?.blur();
    
    this._confirmService.confirm('Do you want to delete this inventory item?')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDelete(item);
        }
      });
  }

  private executeDelete(item: IInventory): void {
    this.isPageLoad = true;
    const deletePayload = { ...item, is_active: false, is_deleted: true };

    this._inventoryService.insertUpdateInventory(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Inventory item deleted', 'success');
            this.fetchInventoryList(); // Refresh current view
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting inventory item', 'error');
        }
      });
  }
}
