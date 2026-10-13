import { Component, inject, OnInit, TemplateRef, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatTableDataSource } from '@angular/material/table';
import { ActivatedRoute } from '@angular/router';
import { finalize } from 'rxjs/operators';

import { IGenricGrid, INavigationaBar } from '../../models/ICommon.model';
import { ITable, ITableZone, TABLE_STATUS_LABELS, TableStatus } from '../../models/ICms.model';
import { CmsFloorService } from '../../services/cms/floor.service';
import { ConfirmationService } from '../../services/confirmation.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { InstanceService } from '../../core/config/instance.service';

/**
 * Table management.
 *
 * Two tabs because zones are the only thing a table cannot own itself: a table
 * row has to name its zone from a list that lives somewhere, and putting both
 * on one screen stops the operator from hunting for "where do I add a Patio?"
 * on a different route.
 *
 * The tables tab is the admin view of the floor. The POS has its own floor view
 * (CmsFloorService.getFloorView) -- this one is for renaming a table, taking
 * one out of service, or correcting a capacity. It deliberately does NOT show
 * open orders as an editable field, because occupancy is not the operator's to
 * set (see SETTABLE_STATUSES below).
 */
@Component({
  selector: 'app-table-list',
  templateUrl: './table-list.component.html',
  styleUrl: './table-list.component.scss'
})
export class TableListComponent implements OnInit {

  //// Inject Services
  private _floorService = inject(CmsFloorService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _dialog = inject(MatDialog);
  private _route = inject(ActivatedRoute);
  private _instance = inject(InstanceService);
  private _fb = inject(FormBuilder);

  /// Dialog templates live in this component's own view. Declaring them inline
  /// (rather than as separate components) keeps the whole screen in six files
  /// and keeps the form's reactive state next to the methods that read it.
  @ViewChild('tableFormTpl') tableFormTpl!: TemplateRef<unknown>;
  @ViewChild('statusFormTpl') statusFormTpl!: TemplateRef<unknown>;
  @ViewChild('zoneFormTpl') zoneFormTpl!: TemplateRef<unknown>;

  //// Constants
  readonly statusLabels = TABLE_STATUS_LABELS;

  /**
   * The statuses an operator may set by hand.
   *
   * 'occupied' is deliberately absent. The backend accepts only
   * available / reserved / cleaning / maintenance on both upsertTable and
   * updateTableStatus, because occupancy belongs to the order lifecycle: a
   * table becomes occupied when an order is opened against it and frees itself
   * when that order is paid and closed. Offering 'occupied' here would let
   * someone mark a table busy with nobody at it, and the POS would then refuse
   * to seat the next guest because it already believes an order is running.
   * The status FILTER below still lists every value, because "show me the
   * occupied tables" is a legitimate thing to want.
   */
  readonly settableStatuses: TableStatus[] = ['available', 'reserved', 'cleaning', 'maintenance'];

  /// Mirrors TABLE_SHAPES in table_schema.py -- square / round / rectangle.
  readonly tableShapes = ['square', 'round', 'rectangle'];

  //// State Properties
  navData: INavigationaBar[] = [];
  selectedTabIndex = 0;

  isPageLoad = false;
  isZoneLoad = false;
  isSaving = false;

  // ---- tables tab ----
  gridSearch = '';
  filterZoneId: number | null = null;
  filterStatus: TableStatus | null = null;

  tableList: ITable[] = [];
  tableDataSource = new MatTableDataSource<ITable>();
  displayedColumns: string[] = ['sr', 'table_number', 'table_name', 'zone_name', 'capacity', 'status', 'is_active', 'actions'];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 };

  /// Zone list doubles as the filter dropdown AND the form's zone picker, so
  /// the operator never sees a zone they cannot then select.
  zoneList: ITableZone[] = [];

  // ---- zones tab ----
  zoneDataSource = new MatTableDataSource<ITableZone>();
  zoneColumns: string[] = ['sr', 'name', 'display_name', 'description', 'display_order', 'table_count', 'is_active', 'actions'];
  isZoneSearch = '';

  //// Request State
  private requestData = {
    page_number: 1,
    page_size: 10,
    search_value: '',
    zone_id: null as number | null,
    status: null as TableStatus | null
  };

  private zoneRequest = { page_number: 1, page_size: 200, search_value: '' };

  //// Form State
  tableForm!: FormGroup;
  zoneForm!: FormGroup;
  statusForm!: FormGroup;

  /// Row currently open in the table form / status dialog. Held on the
  /// component because the dialogs are inline templates, so they can read these
  /// without an injected data object.
  editingTable: ITable | null = null;
  editingZone: ITableZone | null = null;

  /// ids with an in-flight write, so a double click cannot fire two upserts
  /// for the same row (the second would land on a stale copy of the payload).
  busyIds = new Set<number>();

  ngOnInit(): void {
    this.buildForms();
    this.initNavigation();
    this.loadZones();
    this.fetchTables();
  }

  //// ------------------------------------------------------------------
  ////  Navigation
  //// ------------------------------------------------------------------

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: this._instance.homeUrl },
      { displayValue: 'CMS', isClickable: false, isDashboard: false },
      {
        displayValue: this._route.snapshot.data['breadcrumb'] || 'Table Management',
        isClickable: false,
        isDashboard: false
      }
    ];
  }

  //// ------------------------------------------------------------------
  ////  Forms
  //// ------------------------------------------------------------------

  private buildForms(): void {
    this.tableForm = this._fb.group({
      table_number: ['', [Validators.required, Validators.maxLength(20)]],
      table_name: ['', Validators.maxLength(50)],
      capacity: [2, [Validators.required, Validators.min(1), Validators.max(50)]],
      zone_id: [null],
      shape: ['square'],
      is_combinable: [true],
      is_active: [true]
    });

    // status is NOT in the table form. The upsert schema accepts it but the
    // service ignores it for an occupied table, so a status change from this
    // screen has to go through the dedicated dialog where the guard rails
    // around 'occupied' can be explained.
    this.statusForm = this._fb.group({
      status: ['available', Validators.required],
      remarks: ['', Validators.maxLength(255)]
    });

    this.zoneForm = this._fb.group({
      name: ['', [Validators.required, Validators.maxLength(50)]],
      display_name: ['', [Validators.required, Validators.maxLength(50)]],
      description: ['', Validators.maxLength(255)],
      display_order: [0, [Validators.min(0)]],
      is_active: [true]
    });
  }

  //// ------------------------------------------------------------------
  ////  Reads
  //// ------------------------------------------------------------------

  private fetchTables(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;

    this._floorService.getTables(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch tables', 'error');
            return;
          }
          this.tableList = res.data || [];
          this.pageDet.total_docs = res.meta?.total_records || 0;
          this.pageDet.limit = this.requestData.page_size;
          this.tableDataSource.data = this.tableList;
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while fetching the table list', 'error'
        )
      });
  }

  /**
   * Zones for both the filter dropdown and the tables tab's zone picker.
   *
   * The payload carries no table_count (the service deliberately keeps the
   * count out of the list to avoid an aggregate per row), so the zones tab
   * hydrates it separately -- see loadZoneTableCounts.
   */
  private loadZones(): void {
    this._floorService.getZones(this.zoneRequest)
      .pipe(finalize(() => this.isZoneLoad = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch zones', 'error');
            return;
          }
          this.zoneList = res.data || [];
          this.zoneDataSource.data = this.zoneList;
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while fetching zones', 'error'
        )
      });
  }

  private loadZoneTableCounts(): void {
    const rows = this.zoneDataSource.data;
    // Sequential-ish: forkJoin would fire one request per zone in parallel and
    // a cafe with 12 zones is 12 round trips either way, so the honest thing is
    // to fetch only when the Zones tab is actually open.
    rows.forEach((zone, index) => {
      if (!zone.id) return;

      this._floorService.getZoneTableCount(zone.id)
        .subscribe({
          next: (res) => {
            // Mutate the row in place: replacing zoneDataSource.data would
            // rebuild the whole table and lose the scroll position.
            (rows[index] as ITableZone).table_count = res?.status ? res.data?.table_count : undefined;
          },
          error: () => {
            // A count that fails is a missing number, not a reason to blank the
            // zone list -- the operator still needs to see the zones to fix them.
            (rows[index] as ITableZone).table_count = undefined;
          }
        });
    });
  }

  //// ------------------------------------------------------------------
  ////  UI Event Handlers -- tables
  //// ------------------------------------------------------------------

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchTables();
  }

  /**
   * Three characters is the same threshold the inventory lists use: the backend
   * search is a prefix LIKE on table_number, so one or two characters would
   * match most of the floor and make the pager useless. An empty box always
   * applies, otherwise clearing the field looks like it did nothing.
   */
  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchTables();
    }
  }

  onZoneFilter(): void {
    this.requestData.zone_id = this.filterZoneId;
    this.requestData.page_number = 1;
    this.fetchTables();
  }

  onStatusFilter(): void {
    this.requestData.status = this.filterStatus;
    this.requestData.page_number = 1;
    this.fetchTables();
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.filterZoneId = null;
    this.filterStatus = null;
    this.requestData.search_value = '';
    this.requestData.zone_id = null;
    this.requestData.status = null;
    this.requestData.page_number = 1;
    this.fetchTables();
  }

  //// ------------------------------------------------------------------
  ////  Dialogs -- tables
  //// ------------------------------------------------------------------

  onAddTable(): void {
    this.editingTable = null;
    this.tableForm.reset({
      table_number: '',
      table_name: '',
      capacity: 2,
      zone_id: this.filterZoneId,
      shape: 'square',
      is_combinable: true,
      is_active: true
    });
    this._dialog.open(this.tableFormTpl, {
      width: '620px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'tbl-dialog-panel'
    });
  }

  onEditTable(table: ITable): void {
    (document.activeElement as HTMLElement)?.blur();
    this.editingTable = table;
    this.tableForm.reset({
      table_number: table.table_number || '',
      table_name: table.table_name || '',
      capacity: table.capacity || 2,
      zone_id: table.zone_id ?? null,
      shape: table.shape || 'square',
      is_combinable: table.is_combinable ?? true,
      is_active: table.is_active ?? true
    });
    this._dialog.open(this.tableFormTpl, {
      width: '620px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'tbl-dialog-panel'
    });
  }

  saveTable(dialogRef: { close: () => void }): void {
    if (this.tableForm.invalid) {
      this.tableForm.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    const value = this.tableForm.value;

    /**
     * is_deleted is required by the upsert schema on every write, so an update
     * must explicitly say "still live". Table_zone / recipe_category behave the
     * same way; this codebase does soft deletes through the same payload.
     */
    const payload = {
      id: this.editingTable?.id || 0,
      table_number: value.table_number,
      table_name: value.table_name || null,
      capacity: value.capacity,
      zone_id: value.zone_id || null,
      shape: value.shape || null,
      is_combinable: !!value.is_combinable,
      is_active: !!value.is_active,
      is_deleted: false
    };

    this._floorService.upsertTable(payload)
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Table saved successfully', 'success');
            dialogRef.close();
            this.fetchTables();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save the table', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while saving the table', 'error'
        )
      });
  }

  onChangeStatus(table: ITable): void {
    (document.activeElement as HTMLElement)?.blur();
    this.editingTable = table;
    this.statusForm.reset({
      // Never pre-fill with 'occupied': if the table currently IS occupied
      // (an open order is running) that is not a value the operator is allowed
      // to re-save. Default to the harmless 'available'.
      status: this.settableStatuses.includes(table.status as TableStatus)
        ? (table.status as TableStatus)
        : 'available',
      remarks: ''
    });
    this._dialog.open(this.statusFormTpl, {
      width: '460px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'tbl-dialog-panel'
    });
  }

  saveStatus(dialogRef: { close: () => void }): void {
    if (this.statusForm.invalid || !this.editingTable?.id) {
      this.statusForm.markAllAsTouched();
      return;
    }

    const table = this.editingTable;
    const status = this.statusForm.value.status as TableStatus;

    /**
     * Belt and braces: the list below already excludes 'occupied', but this
     * component should never be the reason a bad status reaches the API -- if
     * someone edits the template and re-adds the option, the request is
     * refused here with an explanation instead of 422-ing at the schema.
     */
    if (!this.settableStatuses.includes(status)) {
      this._snackbar.openSnackBar(
        `"${this.statusLabel(status)}" is set by the order lifecycle, not by hand`, 'warn');
      return;
    }

    this.isSaving = true;
    this._floorService.updateTableStatus(table.id!, status, this.statusForm.value.remarks || undefined)
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Status updated successfully', 'success');
            dialogRef.close();
            this.fetchTables();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to update the status', 'error');
          }
        },
        error: (err) => {
          /**
           * 409 here means the table still has an open order. That is not a
           * transient failure and retrying will not help -- the operator has to
           * settle the order first, so the backend's wording is shown verbatim
           * instead of being flattened into "something went wrong".
           */
          const msg = err?.status === 409
            ? (err?.error?.message || 'This table has an open order. Close or cancel the order first.')
            : (err?.error?.message || 'An error occurred while updating the status');
          this._snackbar.openSnackBar(msg, err?.status === 409 ? 'warn' : 'error');
        }
      });
  }

  /**
   * Quick is_active flip from the row, without opening the form.
   *
   * Goes through the same upsert as the edit dialog because is_active lives on
   * the table record, not on a status endpoint -- taking a table out of service
   * and marking it 'maintenance' are different intents.
   */
  onToggleActive(table: ITable, isActive: boolean): void {
    if (!table.id) return;

    this.busyIds.add(table.id);
    this._floorService.upsertTable({
      id: table.id,
      table_number: table.table_number,
      table_name: table.table_name || null,
      capacity: table.capacity,
      zone_id: table.zone_id ?? null,
      shape: table.shape || null,
      is_combinable: !!table.is_combinable,
      is_active: isActive,
      is_deleted: false
    })
      .pipe(finalize(() => this.busyIds.delete(table.id!)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            table.is_active = isActive;
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to update the table', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while updating the table', 'error'
        )
      });
  }

  onDeleteTable(table: ITable): void {
    (document.activeElement as HTMLElement)?.blur();

    this._confirmService
      .confirm(
        'Delete this table?',
        `Table ${table.table_number} will be removed from the floor. Historical orders keep their copy of it.`,
        'Yes, Delete it!'
      )
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDeleteTable(table);
        }
      });
  }

  private executeDeleteTable(table: ITable): void {
    if (!table.id) return;

    this.isPageLoad = true;

    /**
     * There is no DELETE endpoint for reference data in this API -- a delete is
     * an upsert with is_deleted flipped. is_active goes false too so the table
     * stops appearing as selectable the moment it is soft-deleted.
     */
    this._floorService.upsertTable({
      id: table.id,
      table_number: table.table_number,
      table_name: table.table_name || null,
      capacity: table.capacity,
      zone_id: table.zone_id ?? null,
      shape: table.shape || null,
      is_combinable: !!table.is_combinable,
      is_active: false,
      is_deleted: true
    })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Table deleted successfully', 'success');
            this.fetchTables();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete the table', 'error');
          }
        },
        error: (err) => {
          /**
           * The backend 409s a delete on a table that still has an open order
           * ("Close or cancel the order first"). Swallowing that into a generic
           * failure would leave the operator thinking the delete is broken, so
           * the conflict message is surfaced as-is.
           */
          const msg = err?.status === 409
            ? (err?.error?.message || 'This table has an open order. Close or cancel the order first.')
            : (err?.error?.message || 'An error occurred while deleting the table');
          this._snackbar.openSnackBar(msg, err?.status === 409 ? 'warn' : 'error');
        }
      });
  }

  //// ------------------------------------------------------------------
  ////  Zones tab
  //// ------------------------------------------------------------------

  onTabChange(index: number): void {
    if (index === 1) {
      // Counts are only fetched when the tab is opened: a manager who never
      // looks at zones should not pay for one request per zone.
      this.loadZoneTableCounts();
    }
  }

  applyZoneFilter(): void {
    if (this.isZoneSearch.length >= 3 || this.isZoneSearch.length === 0) {
      this.zoneRequest.search_value = this.isZoneSearch;
      this.loadZones();
      if (this.selectedTabIndex === 1) {
        this.loadZoneTableCounts();
      }
    }
  }

  onAddZone(): void {
    this.editingZone = null;
    this.zoneForm.reset({
      name: '',
      display_name: '',
      description: '',
      display_order: this.zoneList.length,
      is_active: true
    });
    this._dialog.open(this.zoneFormTpl, {
      width: '560px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'tbl-dialog-panel'
    });
  }

  onEditZone(zone: ITableZone): void {
    (document.activeElement as HTMLElement)?.blur();
    this.editingZone = zone;
    this.zoneForm.reset({
      name: zone.name || '',
      display_name: zone.display_name || '',
      description: zone.description || '',
      display_order: zone.display_order ?? 0,
      is_active: zone.is_active ?? true
    });
    this._dialog.open(this.zoneFormTpl, {
      width: '560px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'tbl-dialog-panel'
    });
  }

  saveZone(dialogRef: { close: () => void }): void {
    if (this.zoneForm.invalid) {
      this.zoneForm.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    const value = this.zoneForm.value;

    const payload = {
      id: this.editingZone?.id || 0,
      name: value.name,
      display_name: value.display_name,
      description: value.description || null,
      display_order: value.display_order || 0,
      is_active: !!value.is_active,
      is_deleted: false
    };

    this._floorService.upsertZone(payload)
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Zone saved successfully', 'success');
            dialogRef.close();
            this.loadZones();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save the zone', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while saving the zone', 'error'
        )
      });
  }

  onDeleteZone(zone: ITableZone): void {
    (document.activeElement as HTMLElement)?.blur();

    /**
     * The backend does NOT block deleting a zone that still has tables -- it
     * soft-deletes the zone and leaves those tables unzoned ("Unassigned" on
     * the floor). That is recoverable, but only if the operator is told before
     * they click, because afterwards the tables lose their group on the POS
     * grid and the reason is not obvious.
     */
    const count = zone.table_count;
    const warning = count === undefined || count === null
      ? 'Any tables still in this zone will become unassigned on the floor.'
      : `${count} table${count === 1 ? '' : 's'} in this zone will become unassigned on the floor.`;

    this._confirmService
      .confirm('Delete this zone?', warning, 'Yes, Delete it!')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDeleteZone(zone);
        }
      });
  }

  private executeDeleteZone(zone: ITableZone): void {
    if (!zone.id) return;

    this.isZoneLoad = true;
    this._floorService.upsertZone({
      id: zone.id,
      name: zone.name,
      display_name: zone.display_name || zone.name,
      description: zone.description || null,
      display_order: zone.display_order ?? 0,
      is_active: false,
      is_deleted: true
    })
      .pipe(finalize(() => this.isZoneLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Zone deleted successfully', 'success');
            this.loadZones();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete the zone', 'error');
          }
        },
        error: (err) => {
          // 409 = a live zone already owns that name; the backend revives the
          // tombstone on create, so this only happens on a genuine clash.
          const msg = err?.error?.message || 'An error occurred while deleting the zone';
          this._snackbar.openSnackBar(msg, err?.status === 409 ? 'warn' : 'error');
        }
      });
  }

  //// ------------------------------------------------------------------
  ////  Template helpers
  //// ------------------------------------------------------------------

  /**
   * Label lookup with an explicit undefined branch. TableStatus|undefined comes
   * straight off the row, and indexing the Record with it would be a strict
   * template type error for no benefit -- the fallback is the honest answer for
   * a row the server has not stamped yet.
   */
  statusLabel(status?: TableStatus | null): string {
    return status ? this.statusLabels[status] : 'Unknown';
  }

  /** Class fragment so the pill colour comes from the shared status map. */
  statusClass(status?: TableStatus | null): string {
    return status ? `st-${status}` : 'st-unknown';
  }

  zoneName(zoneId?: number | null): string {
    if (!zoneId) return 'Unassigned';
    return this.zoneList.find(z => z.id === zoneId)?.name || 'Unassigned';
  }

  isBusy(id?: number): boolean {
    return !!id && this.busyIds.has(id);
  }

  getSrNo(index: number): number {
    return (this.requestData.page_size * (this.requestData.page_number - 1)) + (index + 1);
  }

  /// Zero-based index for the paginator, which is why requestData stays private.
  get currentPageIndex(): number {
    return this.requestData.page_number - 1;
  }
}