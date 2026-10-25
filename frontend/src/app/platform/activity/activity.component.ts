import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MatPaginatorSelectConfig, PageEvent } from '@angular/material/paginator';
import { finalize } from 'rxjs/operators';
import moment, { Moment } from 'moment';

import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { PAGE_SIZE_SELECT_CONFIG } from '../../shared/paginator-config';
import { IEntityResponse } from '../../models/ICommon.model';
import { IAuditLog } from '../models/platform.model';
import { PlatformAuditService } from '../services/platform-audit.service';

/** One selectable verb in the action filter. Kept in step with the writers:
 * `tenant_management_service`, `super_admin_user_service` and
 * `super_admin_auth_service`. */
interface IActionOption {
  value: string;
  label: string;
  tone: string;
}

const ACTION_OPTIONS: IActionOption[] = [
  { value: 'CREATE_TENANT', label: 'Created hotel', tone: 'success' },
  { value: 'UPDATE_TENANT', label: 'Updated hotel', tone: 'neutral' },
  { value: 'ACTIVATE_TENANT', label: 'Activated hotel', tone: 'success' },
  { value: 'DEACTIVATE_TENANT', label: 'Deactivated hotel', tone: 'warn' },
  { value: 'ARCHIVE_TENANT', label: 'Archived hotel', tone: 'amber' },
  { value: 'RESTORE_TENANT', label: 'Restored hotel', tone: 'neutral' },
  { value: 'CREATE_SUPER_ADMIN', label: 'Created administrator', tone: 'success' },
  { value: 'UPDATE_SUPER_ADMIN', label: 'Updated administrator', tone: 'neutral' },
  { value: 'ACTIVATE_SUPER_ADMIN', label: 'Activated administrator', tone: 'success' },
  { value: 'DEACTIVATE_SUPER_ADMIN', label: 'Deactivated administrator', tone: 'warn' },
  { value: 'RESET_SUPER_ADMIN_PASSWORD', label: 'Reset administrator password', tone: 'amber' },
  { value: 'RESET_SUPER_ADMIN_MFA', label: 'Reset administrator two-factor', tone: 'amber' },
  // Security events on the operators themselves. Written by
  // `SuperAdminAuthService`, so the trail covers sign-in and credentials, not
  // only the tenant/operator management actions.
  { value: 'LOGIN_SUPER_ADMIN', label: 'Signed in', tone: 'success' },
  { value: 'LOGIN_FAILED_SUPER_ADMIN', label: 'Failed sign-in', tone: 'warn' },
  { value: 'LOGOUT_SUPER_ADMIN', label: 'Signed out', tone: 'neutral' },
  { value: 'CHANGE_SUPER_ADMIN_PASSWORD', label: 'Changed own password', tone: 'amber' },
  { value: 'ENABLE_SUPER_ADMIN_MFA', label: 'Enabled two-factor', tone: 'success' },
];

const ENTITY_OPTIONS = [
  { value: 'tenant', label: 'Tenants' },
  { value: 'super_admin', label: 'Administrator' },
];

/**
 * The platform activity feed: the reader for the audit trail every management
 * action writes.
 *
 * Global and newest-first, optionally narrowed by verb, entity or date. The
 * `details` column is the writer's own JSON, shown verbatim rather than re-parsed
 * into a shape the UI would then have to keep in step with each verb.
 */
@Component({
  selector: 'app-platform-activity',
  templateUrl: './activity.component.html',
  styleUrl: './activity.component.scss',
})
export class PlatformActivityComponent {

  private _audit = inject(PlatformAuditService);
  private _snackbar = inject(CustomSnackbarService);
  private _route = inject(ActivatedRoute);

  readonly actionOptions = ACTION_OPTIONS;
  readonly entityOptions = ENTITY_OPTIONS;

  // Shared with every other list page, so the page-size trigger and its
  // option list are sized identically across the HMS and the platform console.
  readonly pageSizeSelect: MatPaginatorSelectConfig = PAGE_SIZE_SELECT_CONFIG;

  readonly displayedColumns = ['created_at', 'actor_email', 'action', 'entity', 'details'];

  logs: IAuditLog[] = [];
  totalRecords = 0;
  pageSize = 10;
  pageIndex = 0;

  actionFilter = '';
  entityFilter = '';
  /** A specific row id, used to show one tenant's or one admin's history. Kept
   * as text so an in-progress entry never throws; only a clean integer is sent. */
  entityIdFilter = '';
  /** Picker-backed since the calendar replaced the native date input, so these
   * hold a Moment rather than the `YYYY-MM-DD` text they used to. Null when
   * unset, and normalised for the API in `load`. */
  dateFrom: Moment | null = null;
  dateTo: Moment | null = null;

  isLoading = false;

  get isRefreshing(): boolean {
    return this.isLoading && this.logs.length > 0;
  }

  ngOnInit(): void {
    // Filters can arrive from the query string -- the tenant and administrator
    // edit screens link here pre-scoped to their own row -- so honour whatever
    // was provided.
    const params = this._route.snapshot.queryParamMap;
    this.entityFilter = params.get('entity_type') ?? '';
    this.actionFilter = params.get('action') ?? '';
    const entityId = params.get('entity_id');
    this.entityIdFilter = entityId && /^\d+$/.test(entityId) ? entityId : '';
    this.load();
  }

  load(): void {
    const entityId = this.entityIdFilter.trim();
    // Build the request before flipping the spinner on. `finalize` only
    // attaches to an observable that was actually created, so a synchronous
    // throw while assembling the query (see `dayBoundary`) would otherwise
    // skip it and leave the spinner running forever.
    const query = {
      page_size: this.pageSize,
      page_number: this.pageIndex + 1,
      action: this.actionFilter || undefined,
      entity_type: this.entityFilter || undefined,
      entity_id: entityId && /^\d+$/.test(entityId) ? Number(entityId) : undefined,
      date_from: this.dayBoundary(this.dateFrom, false),
      // Inclusive of the chosen day: a bare date would parse as midnight and
      // silently drop everything that happened during it.
      date_to: this.dayBoundary(this.dateTo, true),
    };
    this.isLoading = true;
    this._audit.list(query)
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.logs = (resp?.data as IAuditLog[]) ?? [];
          this.totalRecords = resp?.meta?.total_records ?? 0;
        },
        error: (err) => {
          this.logs = [];
          this.totalRecords = 0;
          this._snackbar.openSnackBar(err?.error?.message || 'Could not load activity.', 'error');
        },
      });
  }

  applyFilters(): void {
    this.pageIndex = 0;
    this.load();
  }

  clearFilters(): void {
    this.actionFilter = '';
    this.entityFilter = '';
    this.entityIdFilter = '';
    this.dateFrom = null;
    this.dateTo = null;
    this.pageIndex = 0;
    this.load();
  }

  /** The two calendars clamp each other, so a range can never be built with its
   * ends swapped: whichever end is already chosen greys out the other. */
  get dateFromMax(): Moment | null {
    return this.dateTo;
  }

  get dateToMin(): Moment | null {
    return this.dateFrom;
  }

  /** The API takes a plain `YYYY-MM-DDTHH:mm:ss` local stamp. The picker's
   * value is a Moment under the app's date adapter, but this must not assume
   * it: a plain `Date` used to reach `value.isValid()` here, throw, and escape
   * `load()` before `finalize` could attach -- which left the spinner running
   * forever. `moment()` normalises a Moment, a Date or an ISO string alike; an
   * unparseable value is treated as unset rather than sent as `Invalid date`. */
  private dayBoundary(value: Moment | Date | null, endOfDay: boolean): string | undefined {
    if (!value) {
      return undefined;
    }
    const day = moment(value);
    if (!day.isValid()) {
      return undefined;
    }
    return `${day.format('YYYY-MM-DD')}T${endOfDay ? '23:59:59' : '00:00:00'}`;
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.load();
  }

  /** Human label for a verb, falling back to the raw action so a new one is
   * legible before this list is updated. */
  actionLabel(action: string): string {
    return this.actionOptions.find((option) => option.value === action)?.label ?? action;
  }

  actionTone(action: string): string {
    return this.actionOptions.find((option) => option.value === action)?.tone ?? 'neutral';
  }

  entityLabel(log: IAuditLog): string {
    const type = log.entity_type === 'tenant' ? 'Tenant' : 'Administrator';
    return log.entity_id != null ? `${type} #${log.entity_id}` : type;
  }

  /** Pretty-print the stored JSON for readability; leave anything unparseable
   * as-is rather than hiding it. */
  prettyDetails(details: string | null): string {
    if (!details) {
      return '—';
    }
    try {
      return JSON.stringify(JSON.parse(details), null, 2);
    } catch {
      return details;
    }
  }
}
