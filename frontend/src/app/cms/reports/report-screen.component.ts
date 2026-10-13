import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { Observable } from 'rxjs';

import { IEntityResponse } from '../../models/ICommon.model';
import {
  ReportRange, REPORT_PRESETS, ISalesSummary, IItemSales,
  IDailyTrend, IVoidReport, IKitchenReport, ICustomerReport
} from '../../models/ICms.model';
import { CmsReportService } from '../../services/cms/report.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';

interface ReportTab {
  key: string;
  label: string;
  icon: string;
}

/**
 * Reports screen — six reports behind one shared date-range control.
 *
 * Only the ACTIVE tab is fetched. Loading all six on a range change would mean
 * six round trips to draw one screen, and half of them would be discarded
 * before anyone looked at them.
 */
@Component({
  selector: 'app-report-screen',
  standalone: false,
  templateUrl: './report-screen.component.html',
  styleUrl: './report-screen.component.scss'
})
export class ReportScreenComponent implements OnInit, OnDestroy {
  private _reportService = inject(CmsReportService);
  private _snackbar = inject(CustomSnackbarService);

  private _destroy$ = new Subject<void>();

  isPageLoad = false;
  activeTab = 0;

  reportTabs: ReportTab[] = [
    { key: 'sales', label: 'Sales Summary', icon: 'attach_money' },
    { key: 'items', label: 'Item Sales', icon: 'inventory_2' },
    { key: 'trend', label: 'Daily Trend', icon: 'show_chart' },
    { key: 'voids', label: 'Void / Loss', icon: 'report_problem' },
    { key: 'kitchen', label: 'Kitchen Perf.', icon: 'kitchen' },
    { key: 'customers', label: 'Customers', icon: 'people' }
  ];

  reportPresets = REPORT_PRESETS;

  /**
   * Range + per-tab controls as a single reactive form.
   *
   * These were previously read with document.getElementById, which is a bug
   * waiting to happen: it is untyped, invisible to Angular's change detection
   * (so `include_dead_stock` toggling did nothing until a re-fetch by some
   * other route), and it silently returns null under test or SSR, coercing
   * every option to its default without an error.
   */
  form = new FormGroup({
    range: new FormControl<ReportRange>('today', { nonNullable: true }),
    from_date: new FormControl<Date | null>(null),
    to_date: new FormControl<Date | null>(null),

    // Item Sales controls
    sort_by: new FormControl<'quantity' | 'revenue'>('quantity', { nonNullable: true }),
    item_limit: new FormControl<number>(20, { nonNullable: true }),
    include_dead_stock: new FormControl<boolean>(false, { nonNullable: true }),
    station: new FormControl<string | null>(null),

    // Daily Trend
    include_zero_days: new FormControl<boolean>(true, { nonNullable: true }),

    // Void report
    group_by_staff: new FormControl<boolean>(true, { nonNullable: true }),
    void_limit: new FormControl<number>(100, { nonNullable: true }),

    // Kitchen
    include_by_item: new FormControl<boolean>(true, { nonNullable: true }),

    // Customers
    customer_limit: new FormControl<number>(20, { nonNullable: true })
  });

  // Results
  salesSummary: ISalesSummary | null = null;
  itemSales: IItemSales | null = null;
  dailyTrend: IDailyTrend | null = null;
  voidReport: IVoidReport | null = null;
  kitchenReport: IKitchenReport | null = null;
  customerReport: ICustomerReport | null = null;

  /** Resolved window echoed back by the server, shown so it can be verified. */
  rangeMeta: any = null;

  navData: any[] = [
    { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/cms/dashboard' },
    { displayValue: 'Reports', isClickable: false, isDashboard: false }
  ];

  Math = Math;

  ngOnInit(): void {
    // Preset changes clear any custom dates and refetch. Custom waits for
    // both dates, because the backend rejects a half-filled range.
    this.form.get('range')!.valueChanges
      .pipe(takeUntil(this._destroy$))
      .subscribe((range) => {
        if (range !== 'custom') {
          this.form.patchValue(
            { from_date: null, to_date: null },
            { emitEvent: false }
          );
          this.loadActiveTab();
        }
      });

    this.loadActiveTab();
  }

  ngOnDestroy(): void {
    this._destroy$.next();
    this._destroy$.complete();
  }

  onTabChange(index: number): void {
    this.activeTab = index;
    this.loadActiveTab();
  }

  /** Refetch the active tab after a per-tab control changes. */
  onControlChange(): void {
    this.loadActiveTab();
  }

  onCustomDateChange(): void {
    const from = this.form.get('from_date')!.value;
    const to = this.form.get('to_date')!.value;
    if (from && to) {
      this.loadActiveTab();
    }
  }

  isCustom(): boolean {
    return this.form.get('range')!.value === 'custom';
  }

  /** Build the payload every report endpoint expects. */
  private buildPayload(): any {
    const range = this.form.get('range')!.value;
    const payload: any = { range };

    if (range === 'custom') {
      const from = this.form.get('from_date')!.value;
      const to = this.form.get('to_date')!.value;
      if (from && to) {
        payload.from_date = this.formatDate(from);
        payload.to_date = this.formatDate(to);
      }
    }

    return payload;
  }

  private loadActiveTab(): void {
    const payload = this.buildPayload();
    this.isPageLoad = true;

    switch (this.activeTab) {
      case 0: this.fetch(() => this._reportService.getSalesSummary(
        payload.range, true, true)); break;
      case 1: this.fetch(() => this._reportService.getItemSales(payload.range, {
        sort_by: this.form.get('sort_by')!.value,
        limit: this.form.get('item_limit')!.value,
        include_dead_stock: this.form.get('include_dead_stock')!.value,
        station: this.form.get('station')!.value
      })); break;
      case 2: this.fetch(() => this._reportService.getDailyTrend(
        payload.range, this.form.get('include_zero_days')!.value)); break;
      case 3: this.fetch(() => this._reportService.getVoidReport(payload.range, {
        group_by_staff: this.form.get('group_by_staff')!.value,
        limit: this.form.get('void_limit')!.value
      })); break;
      case 4: this.fetch(() => this._reportService.getKitchenPerformance(
        payload.range, this.form.get('include_by_item')!.value)); break;
      case 5: this.fetch(() => this._reportService.getCustomerReport(
        payload.range, this.form.get('customer_limit')!.value)); break;
    }
  }

  /**
   * Run one report call, assign it to the right field, and clear the spinner.
   *
   * A failed report must not leave the previous tab's numbers on screen — a
   * stale revenue figure under a fresh date heading is worse than no figure.
   */
  private fetch(call: () => Observable<IEntityResponse>): void {
    call().subscribe({
      next: (res) => {
        if (res?.status) {
          this.assignResult(res.data);
          this.rangeMeta = res.data?.range ?? null;
        } else {
          this.clearResult();
          this._snackbar.openSnackBar(res?.message || 'Failed to load report', 'error');
        }
        this.isPageLoad = false;
      },
      error: (err) => {
        this.clearResult();
        this._snackbar.openSnackBar(
          err?.error?.message || 'Failed to load report', 'error');
        this.isPageLoad = false;
      }
    });
  }

  private assignResult(data: any): void {
    switch (this.activeTab) {
      case 0: this.salesSummary = data; break;
      case 1: this.itemSales = data; break;
      case 2:
        this.dailyTrend = data;
        // Precomputed because Angular template syntax has no arrow functions,
        // so series.map(...) inside a binding is a parse error.
        this.trendMax = this.maxOf(
          ((data?.series ?? []) as IDailyTrend['series']).map(s => Number(s.revenue) || 0)
        );
        break;
      case 3: this.voidReport = data; break;
      case 4: this.kitchenReport = data; break;
      case 5: this.customerReport = data; break;
    }
  }

  private clearResult(): void {
    switch (this.activeTab) {
      case 0: this.salesSummary = null; break;
      case 1: this.itemSales = null; break;
      case 2: this.dailyTrend = null; break;
      case 3: this.voidReport = null; break;
      case 4: this.kitchenReport = null; break;
      case 5: this.customerReport = null; break;
    }
    this.rangeMeta = null;
  }

  private formatDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  /**
   * CSV export of whatever is currently on screen.
   *
   * Values are stringified and quote-escaped rather than left as raw object
   * text: a customer name containing a comma would otherwise shift every
   * following column by one in Excel.
   */
  exportCsv(rows: any[], filename: string): void {
    if (!rows || rows.length === 0) {
      this._snackbar.openSnackBar('No data to export', 'warn');
      return;
    }

    const headers = Object.keys(rows[0]);
    const escape = (value: any): string => {
      const text = value === null || value === undefined ? '' : String(value);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };

    const csv = [
      headers.join(','),
      ...rows.map(row => headers.map(h => escape(row[h])).join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    this._snackbar.openSnackBar('CSV exported', 'success');
  }

  /**
   * Row height for a div-based bar, as a % of the tallest bar in its set.
   * Guarded against a zero max so an all-zero day renders a flat baseline
   * instead of dividing by zero into NaN.
   */
  barHeight(value: number, max: number): number {
    if (!max || max <= 0) return 2;
    return Math.max((value / max) * 100, 2);
  }

  maxOf(values: number[]): number {
    return values.length ? Math.max(...values) : 0;
  }

  /**
   * Tallest day in the trend, computed on assignment rather than in the
   * template. Angular expression syntax has no arrow functions, so
   * `series.map(s => +s.revenue)` inside a binding is a parse error, and
   * recomputing it per row on every change-detection pass would be wasteful
   * besides.
   */
  trendMax: number = 0;

  /** Tallest hour for one trading day, so each day's bars scale to itself. */
  hourlyMax(hours: any[]): number {
    return this.maxOf((hours || []).map(h => Number(h.revenue) || 0));
  }

  /**
   * Whether any trade happened at all in the period.
   *
   * Without this, a cafe closed all week renders 24 identical baseline bars
   * per day and the chart implies steady trade that never occurred.
   */
  hasAnyHourlyRevenue(summary: ISalesSummary | null): boolean {
    if (!summary?.hourly) return false;
    return Object.values(summary.hourly)
      .some((hours: any) => (hours || []).some((h: any) => Number(h.revenue) > 0));
  }
}