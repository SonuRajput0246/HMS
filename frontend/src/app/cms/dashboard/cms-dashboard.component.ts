import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { interval, Subscription } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { IGenricGrid } from '../../models/ICommon.model';
import { CmsOrderService } from '../../services/cms/order.service';
import { CmsFloorService } from '../../services/cms/floor.service';
import { CmsKdsService } from '../../services/cms/kds.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { CurrencyInrPipe } from '../../pipes/currency-inr.pipe';
import { MaterialModule } from '../../shared/material-module';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';

@Component({
  selector: 'app-cms-dashboard',
  standalone: false,
  templateUrl: './cms-dashboard.component.html',
  styleUrl: './cms-dashboard.component.scss'
})
export class CmsDashboardComponent implements OnInit, OnDestroy {
  private _orderService = inject(CmsOrderService);
  private _floorService = inject(CmsFloorService);
  private _kdsService = inject(CmsKdsService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);

  private _destroy$ = new Subscription();
  private _kdsRefreshSub: Subscription | null = null;

  isPageLoad = false;
  summary: any = null;
  kdsTickets: any[] = [];
  kdsSummary: any = null;

  /**
   * Floor tallies. Typed loosely because the keys come from a TableStatus
   * union while the values are counts — declaring the full union here would
   * make every `floorCounts?.available` read fail strict index checking
   * when only some keys are guaranteed present.
   */
  floorCounts: Record<string, number> | null = null;

  navData: any[] = [];

  ngOnInit(): void {
    this.initNavigation();
    this.loadDashboardData();
    this.startKdsAutoRefresh();
  }

  ngOnDestroy(): void {
    this._destroy$.unsubscribe();
    if (this._kdsRefreshSub) {
      this._kdsRefreshSub.unsubscribe();
    }
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: true, redirectValue: '/cms/dashboard' },
      { displayValue: 'Dashboard', isClickable: false, isDashboard: true }
    ];
  }

  private loadDashboardData(): void {
    this.isPageLoad = true;

    // Load POS summary
    this._orderService.getSummary(true).subscribe({
      next: (res) => {
        if (res?.status) {
          this.summary = res.data;
          this.isPageLoad = false;
        } else {
          this._snackbar.openSnackBar(res?.message || 'Failed to load summary', 'error');
          this.isPageLoad = false;
        }
      },
      error: (err) => {
        this._snackbar.openSnackBar(err.error?.message || 'Failed to load dashboard', 'error');
        this.isPageLoad = false;
      }
    });

    // Load KDS tickets for the dashboard panel
    this.loadKdsTickets();

    // Load floor counts
    this.loadFloorCounts();
  }

  /**
   * Tallies the whole floor for the KPI cards.
   *
   * Paged rather than asking for one big page. This used to request
   * `page_size: 1000`, which the schema caps at 500, so the call returned 400
   * on every load and -- because the subscribe had no error handler -- left the
   * cards showing zero, indistinguishable from a genuinely empty venue.
   *
   * Paging to `meta.last_page` rather than raising the request size keeps the
   * tally exact: a venue with more tables than one page is counted in full
   * instead of quietly undercounting, and the deliberate server-side cap is
   * left alone.
   */
  private loadFloorCounts(): void {
    const pageSize = 500;

    this._floorService.getTables({ page_size: pageSize, page_number: 1 }).subscribe({
      next: (res) => {
        if (!res?.status) {
          this._snackbar.openSnackBar(res?.message || 'Failed to load floor', 'error');
          return;
        }

        const rows: any[] = res.data ?? [];
        const lastPage = Number((res as any).meta?.last_page ?? 1);

        if (lastPage <= 1) {
          this.floorCounts = this.calculateFloorCounts(rows);
          return;
        }

        let collected = [...rows];
        const pending: number[] = [];
        for (let page = 2; page <= lastPage; page++) {
          pending.push(page);
        }

        // Sequential rather than forkJoin: a venue large enough to need several
        // pages should not have every page requested at once, and one failed
        // page degrades to a partial count with a warning instead of discarding
        // the pages that did load.
        const nextPage = () => {
          const page = pending.shift();
          if (page === undefined) {
            this.floorCounts = this.calculateFloorCounts(collected);
            return;
          }
          this._floorService.getTables({ page_size: pageSize, page_number: page })
            .subscribe({
              next: (more) => {
                if (more?.status) {
                  collected = collected.concat(more.data ?? []);
                } else {
                  this._snackbar.openSnackBar(
                    more?.message || 'Failed to load part of the floor', 'error');
                }
                nextPage();
              },
              error: () => {
                this._snackbar.openSnackBar('Failed to load part of the floor', 'error');
                nextPage();
              }
            });
        };
        nextPage();
      },
      error: (err) => {
        this._snackbar.openSnackBar(err.error?.message || 'Failed to load floor', 'error');
      }
    });
  }

  private loadKdsTickets(): void {
    this._kdsService.getTickets({ order_by: 'oldest_first' }).subscribe({
      next: (res) => {
        if (res?.status) {
          this.kdsTickets = res.data.tickets || [];
          this.kdsSummary = res.data.summary;
        }
      }
    });
  }

  private startKdsAutoRefresh(): void {
    this._kdsRefreshSub = interval(30000).subscribe(() => {
      this.loadKdsTickets();
    });
  }

  /**
   * Tallies tables by status for the KPI cards.
   *
   * Record<string, number> rather than a fixed shape: the server may add a
   * table status, and an unknown one should still be counted rather than
   * tripping an index-signature error at compile time.
   */
  private calculateFloorCounts(tables: any[]): Record<string, number> {
    const counts: Record<string, number> = {
      available: 0, occupied: 0, reserved: 0, cleaning: 0, maintenance: 0, total: 0
    };

    for (const table of tables ?? []) {
      const status = table?.status;
      if (status && counts.hasOwnProperty(status)) {
        counts[status]++;
      }
      counts['total']++;
    }

    return counts;
  }

  navigateTo(route: string): void {
    this._router.navigate([route]);
  }

  getWaitColor(minutes: number | undefined): string {
    if (!minutes) return '';
    if (minutes >= 20) return 'warn';
    if (minutes >= 10) return 'accent';
    return '';
  }

  formatTime(dateString: string | undefined): string {
    if (!dateString) return '--:--';
    return new Date(dateString).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
}