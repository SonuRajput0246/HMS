import { Component, inject, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';

import { TemplateService } from '../../../services/template.service';
import { CommonService } from '../../../services/common.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { IEnumOption, IGenricGrid, INavigationaBar } from '../../../models/ICommon.model';
import { ITemplate, ITemplateListRequest } from '../../../models/IAdmin.model';

@Component({
  selector: 'app-list-template',
  templateUrl: './list.component.html',
  styleUrl: './list.component.scss'
})
export class ListTemplateComponent {

  private _templateService = inject(TemplateService);
  private _commonService = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private _confirmService = inject(ConfirmationService);

  private readonly STORAGE_KEY = 'hms_templateList';

  /// Delivery channels for the filter dropdown and the grid's channel pill,
  /// from the `template_channel` enum definition. Both were hardcoded.
  channels: IEnumOption[] = [];
  isChannelLoading = false;

  navData: INavigationaBar[] = [];
  isPageLoad = false;
  gridSearch = '';
  channelFilter: string = '';
  statusFilter: string = '';

  templateList: ITemplate[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 } as IGenricGrid;
  displayedColumns: string[] = ['sr', 'code', 'name', 'channel', 'preview', 'status', 'actions'];
  dataSource = new MatTableDataSource<ITemplate>();

  requestData: ITemplateListRequest = {
    page_number: 1,
    page_size: 10,
    search_value: '',
    /// null, not '': the backend validates channel with OneOf and 400s on an
    /// empty string. See ITemplateListRequest.
    channel: null,
    is_active: null
  } as ITemplateListRequest;

  @ViewChild(MatPaginator) paginator!: MatPaginator;

  ngOnInit(): void {
    this.initNavigation();
    this.fetchChannels();
    this.loadInitialData();
  }

  /**
   * Load the channel options for the filter and the grid pills.
   *
   * Non-fatal: on failure the filter falls back to an "All" only list and the
   * grid shows the raw key via channelLabel. A dead dropdown must not stop an
   * operator reaching the templates they need to fix.
   */
  private fetchChannels(): void {
    this.isChannelLoading = true;
    this._commonService.getEnumOptions('template_channel')
      .pipe(finalize(() => this.isChannelLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.channels = res.data || [];
          }
        },
        error: () => {
          this.channels = [];
        }
      });
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Template Management', isClickable: false, isDashboard: false }
    ];
  }

  private loadInitialData(): void {
    const savedState = localStorage.getItem(this.STORAGE_KEY);
    if (savedState) {
      this.requestData = JSON.parse(savedState);
      this.gridSearch = this.requestData.search_value || '';
      this.channelFilter = this.requestData.channel || '';
      this.statusFilter = this.requestData.is_active === null || this.requestData.is_active === undefined
        ? '' : (this.requestData.is_active ? 'active' : 'inactive');
    }
    this.fetchTemplateList();
  }

  private fetchTemplateList(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.requestData));

    this._templateService.getTemplates(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.templateList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.templateList;

            /// Deleting the last row on a page would otherwise leave the grid
            /// blank. Step back a page until something is in view.
            if (this.templateList.length === 0 && (this.requestData.page_number ?? 0) > 1) {
              this.requestData.page_number!--;
              this.fetchTemplateList();
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch template list', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching template list';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchTemplateList();
  }

  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchTemplateList();
    }
  }

  applySelectFilter(): void {
    this.requestData.page_number = 1;

    this.requestData.channel = this.channelFilter
      ? this.channelFilter as any
      : null;

    this.requestData.is_active = this.statusFilter === ''
      ? null
      : this.statusFilter === 'active';

    this.fetchTemplateList();
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.channelFilter = '';
    this.statusFilter = '';
    this.requestData.page_number = 1;
    this.requestData.channel = null;
    this.requestData.is_active = null;
    this.fetchTemplateList();
  }

  onEdit(item: ITemplate): void {
    this._router.navigate(['hms/templates/update-template', item.id]);
  }

  onPreview(item: ITemplate): void {
    this._router.navigate(['hms/templates/update-template', item.id]);
  }

  onDelete(item: ITemplate): void {
    (document.activeElement as HTMLElement)?.blur();

    /// Seeded templates are protected server-side with a 400, so do not offer
    /// the action the API is guaranteed to refuse.
    if (item.is_system) {
      this._snackbar.openSnackBar(
        'System templates cannot be deleted. Set them inactive instead.',
        'error'
      );
      return;
    }

    this._confirmService.confirm(
      `Are you sure you want to delete "${item.code}"? This cannot be undone.`
    ).then((result) => {
      if (result.isConfirmed) {
        this.executeDelete(item);
      }
    });
  }

  private executeDelete(item: ITemplate): void {
    this.isPageLoad = true;

    /// Soft delete through the same upsert endpoint the rest of the app uses.
    const deletePayload = {
      id: item.id,
      code: item.code,
      name: item.name,
      channel: item.channel,
      subject_template: null,
      title_template: null,
      message_template: 'deleted',
      variables: item.variables || [],
      is_active: false,
      is_deleted: true
    };

    this._templateService.upsertTemplate(deletePayload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Template deleted successfully', 'success');
            this.fetchTemplateList();
          } else {
            this._snackbar.openSnackBar(res.message || 'Failed to delete template', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(err.error?.message || 'Error deleting template', 'error');
        }
      })
  }

  /**
   * Display label for a channel key, from the loaded enum options.
   *
   * Falls back to the raw key rather than an em dash: a template stored with a
   * channel that is not (or no longer) an active option should still show which
   * channel it is, since that is exactly what an operator needs to see to fix
   * it. The old ternary mapped anything unrecognised to '—'.
   */
  channelLabel(channel?: string | null): string {
    if (!channel) return '—';
    const found = this.channels.find(c => c.option_key === channel);
    return found?.option_label || channel;
  }

  /// Icon for a channel key, with a fallback. `icon` is null for enums that do
  /// not define one, and <mat-icon> renders an empty box for a null name.
  channelIcon(channel?: string | null): string {
    const found = this.channels.find(c => c.option_key === channel);
    return found?.icon || 'mail';
  }
}