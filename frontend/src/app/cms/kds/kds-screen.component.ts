import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin, interval } from 'rxjs';
import { finalize } from 'rxjs/operators';

import {
  IKdsBoard,
  IKdsItem,
  IKdsStationSummary,
  IKdsTicket,
  PREP_STATUS_LABELS,
  PrepStatus,
  STATION_LABELS,
  Station,
  toAmount
} from '../../models/ICms.model';
import { CmsKdsService } from '../../services/cms/kds.service';
import { ConfirmationService } from '../../services/confirmation.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';

/** How often the board re-reads itself. */
const BOARD_POLL_MS = 10000;

/** Minutes before a ticket stops being "on time" and starts being amber. */
const WAIT_WARN_MINUTES = 10;

/** ...and before it goes red, i.e. a chef should already be shouting about it. */
const WAIT_LATE_MINUTES = 20;

/**
 * The three states the kitchen is allowed to set, spelled out as a local union
 * rather than trusting `PrepStatus`.
 *
 * `voided` is server-set only -- voiding is a cashier action that needs a
 * reason, and the API's validator rejects it outright. Narrowing the parameter
 * type here turns "never send voided" from a comment into something the
 * TypeScript compiler enforces: `setPrep(item, 'voided')` will not compile.
 */
type SettablePrepStatus = Extract<PrepStatus, 'pending' | 'preparing' | 'ready'>;

/**
 * Kitchen display system.
 *
 * Built for a pass, not a desk: high contrast, oversized type, and hit targets
 * big enough to find with a wet hand at arm's length. Nothing here is a hover
 * affordance -- every action is a tap that works on the first try.
 *
 * Unlike the POS, the board polls unconditionally. There is no transaction in
 * progress to disturb, and a ticket that appears 10 seconds late is a guest
 * waiting on food.
 */
@Component({
  selector: 'app-kds-screen',
  templateUrl: './kds-screen.component.html',
  styleUrl: './kds-screen.component.scss'
})
export class KdsScreenComponent implements OnInit {

  //// Inject Services
  private _kdsService = inject(CmsKdsService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirm = inject(ConfirmationService);
  private _destroyRef = inject(DestroyRef);

  //// Constants
  readonly PREP_STATUS_LABELS = PREP_STATUS_LABELS;
  readonly WAIT_WARN_MINUTES = WAIT_WARN_MINUTES;
  readonly WAIT_LATE_MINUTES = WAIT_LATE_MINUTES;

  //// State Properties
  /** Blocking overlay, raised only for the very first paint. */
  isPageLoad = false;
  /**
   * A BOARD READ is in flight — the timer poll, or the re-read that follows a
   * write. Deliberately NOT shared with line writes: those track their own
   * per-line / per-ticket ids, because a write that also set this flag would
   * block the very re-read it needs in order to see its own result.
   */
  isBusy = false;

  tickets: IKdsTicket[] = [];
  stations: IKdsStationSummary[] = [];
  /** `null` means every station — the "All stations" tab. */
  activeStation: Station | null = null;
  /** Plated lines come back onto the board so a chef can spot-check or requeue. */
  includeReady = false;

  serverTime = '';
  summary = { pending: 0, preparing: 0, ready: 0 };

  /** Per-line in-flight ids, so one tap greys one row instead of the board. */
  private _pendingLines = new Set<number>();
  /** Tickets with a bump in flight, for the same reason. */
  private _pendingBumps = new Set<number>();

  ngOnInit(): void {
    this.load();

    interval(BOARD_POLL_MS)
      .pipe(takeUntilDestroyed(this._destroyRef))
      .subscribe(() => this.poll());
  }

  //// ------------------------------------------------------------------
  ////  Derived read models
  //// ------------------------------------------------------------------

  get stationLabel(): string {
    return this.activeStation ? this.labelForStation(this.activeStation) : 'All stations';
  }

  /** Outstanding lines across every station — the number on the "All" tab. */
  get totalOutstanding(): number {
    return this.stations.reduce((sum, s) => sum + (s.total ?? 0), 0);
  }

  get ticketCount(): number {
    return this.tickets.length;
  }

  isLineBusy(item: IKdsItem): boolean {
    return this._pendingLines.has(item.id);
  }

  isTicketBusy(ticket: IKdsTicket): boolean {
    return this._pendingBumps.has(ticket.order_id);
  }

  //// ------------------------------------------------------------------
  ////  Loading
  //// ------------------------------------------------------------------

  /**
   * The board + its station badges, in one read.
   *
   * Both callers share this deliberately. `load()` and `poll()` are the same
   * question asked with a different sense of urgency, and duplicating the
   * query here would let them drift -- at which point the tab badges describe
   * a different board than the one on screen, which is worse than either.
   */
  private readBoard() {
    return forkJoin({
      board: this._kdsService.getTickets({
        station: this.activeStation,
        order_by: 'oldest_first',
        include_ready: this.includeReady
      }),
      stations: this._kdsService.getStationSummary()
    });
  }

  /**
   * First paint. Blocking, and loud on failure: a chef staring at an empty
   * board has no way to tell "no orders" from "the screen is broken".
   */
  private load(): void {
    this.isPageLoad = true;
    this.readBoard()
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: ({ board, stations }) => {
          if (!board?.status || !stations?.status) {
            this._snackbar.openSnackBar(
              board?.message || stations?.message || 'Failed to load the kitchen board',
              'error'
            );
            return;
          }
          this.adoptBoard(board.data as IKdsBoard);
          this.stations = (stations.data?.stations ?? []) as IKdsStationSummary[];
        },
        error: (err) => this.fail(err, 'Could not load the kitchen board')
      });
  }

  /**
   * Background refresh. Silent on failure: the next tick is 10 seconds away,
   * and a board that toasts an error every 10 seconds trains the kitchen to
   * ignore every toast on it.
   */
  private poll(): void {
    // A read already in flight; a second one would just race the first.
    if (this.isBusy) return;
    this.isBusy = true;
    this.readBoard()
      .pipe(finalize(() => this.isBusy = false))
      .subscribe({
        next: ({ board, stations }) => {
          if (board?.status) this.adoptBoard(board.data as IKdsBoard);
          if (stations?.status) this.stations = (stations.data?.stations ?? []) as IKdsStationSummary[];
        },
        error: () => { /* retried on the next tick */ }
      });
  }

  private adoptBoard(board: IKdsBoard): void {
    this.tickets = board?.tickets ?? [];
    this.serverTime = board?.server_time ?? '';
    if (board?.summary) this.summary = board.summary;
  }

  /** Manual refresh. The 10s poll is the safety net; this is for right now. */
  refreshNow(): void {
    this.poll();
  }

  onStationChange(station: Station | null): void {
    if (station === this.activeStation) return;
    this.activeStation = station;
    // A station change invalidates every ticket id on screen.
    this._pendingLines.clear();
    this._pendingBumps.clear();
    this.load();
  }

  /**
   * Plated lines are hidden by default so the board only shows what still needs
   * hands on it. Turning them on is how a head chef checks a plate went out, or
   * requeues a line that went cold.
   */
  onToggleIncludeReady(includeReady: boolean): void {
    this.includeReady = includeReady;
    this._pendingLines.clear();
    this._pendingBumps.clear();
    this.load();
  }

  //// ------------------------------------------------------------------
  ////  Line actions
  //// ------------------------------------------------------------------

  onStart(item: IKdsItem): void {
    this.setPrep(item, 'preparing');
  }

  onReady(item: IKdsItem): void {
    // pending -> ready is legal in one tap. Most KDS screens work as
    // "tap when it leaves the pass", and forcing a tap-to-start first
    // doubles the taps on every single dish.
    this.setPrep(item, 'ready');
  }

  /** Requeue a plated line. Restarts its timers server-side. */
  onRequeue(item: IKdsItem): void {
    this.setPrep(item, 'pending');
  }

  /**
   * The only write path for a line's kitchen state.
   *
   * `status` is typed `SettablePrepStatus`, so 'voided' is not a value this
   * method can be called with. That matters because the model file and the API
   * both list 'voided' as a real `PrepStatus` — without the narrowing, a
   * template-driven loop would happily send it and the server would reject
   * every one of those taps.
   */
  private setPrep(item: IKdsItem, status: SettablePrepStatus): void {
    if (this._pendingLines.has(item.id)) return;

    this._pendingLines.add(item.id);

    this._kdsService.updatePrepStatus(item.order_id, item.id, status)
      .pipe(finalize(() => this._pendingLines.delete(item.id)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            // Re-read rather than patching: the same write also advances the
            // ORDER header (preparing -> ready), so a local edit would leave
            // the till showing a stale order status.
            this.poll();
          } else {
            this._snackbar.openSnackBar(res?.message || `Could not update ${item.item_name}`, 'error');
          }
        },
        error: (err) => this.fail(err, `Could not update ${item.item_name}`)
      });
  }

  //// ------------------------------------------------------------------
  ////  Ticket actions
  //// ------------------------------------------------------------------

  /**
   * "Bump all" is the one genuinely irreversible thing on this screen: it
   * plates every remaining line on the ticket at the current station with no
   * per-line review. Hence the confirmation, unlike every single-line tap.
   */
  async onBumpAll(ticket: IKdsTicket): Promise<void> {
    if (this._pendingBumps.has(ticket.order_id)) return;

    const pendingCount = this.countOutstanding(ticket);
    const stationText = this.activeStation ? ` on ${this.labelForStation(this.activeStation)}` : '';

    const answer = await this._confirm.confirm(
      'Bump the whole ticket?',
      `Mark all ${pendingCount} outstanding item(s) ready${stationText} on ${ticket.order_number}? Individual lines cannot be undone once bumped.`,
      'Yes, bump all'
    );
    if (!answer.isConfirmed) return;

    this._pendingBumps.add(ticket.order_id);

    this._kdsService.bumpOrder(ticket.order_id, this.activeStation)
      .pipe(finalize(() => this._pendingBumps.delete(ticket.order_id)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Ticket bumped', 'success');
            this.poll();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not bump the ticket', 'error');
          }
        },
        // 409 here means another station (or another screen) already finished
        // this pass — the state the chef wanted is already true.
        error: (err) => {
          if (err?.status === 409) {
            this.poll();
            this._snackbar.openSnackBar('Those items are already done', 'info');
            return;
          }
          this.fail(err, 'Could not bump the ticket');
        }
      });
  }

  /** Lines on this ticket that are not plated and not voided. */
  countOutstanding(ticket: IKdsTicket): number {
    return ticket.items.filter(i => i.prep_status === 'pending' || i.prep_status === 'preparing').length;
  }

  //// ------------------------------------------------------------------
  ////  Template helpers
  //// ------------------------------------------------------------------

  /**
   * `station` is nullable on the way out: an order line added before the recipe
   * had a station comes back as null and the server buckets it under
   * "unassigned". Falling back to the raw value keeps such a tab readable
   * instead of blank.
   */
  labelForStation(station: Station | null | undefined): string {
    if (!station) return 'Unassigned';
    return STATION_LABELS[station] ?? station;
  }

  prepLabel(status?: PrepStatus): string {
    return status ? (PREP_STATUS_LABELS[status] ?? status) : 'Unknown';
  }

  /**
   * Wait colour. The band boundaries are the whole point of the badge -- a
   * chef triages on amber vs red long before they read the number -- so the
   * class is derived once here rather than in three separate ngClass bindings.
   */
  waitClass(minutes: number): 'wait-ok' | 'wait-warn' | 'wait-late' {
    const wait = toAmount(minutes);
    if (wait >= WAIT_LATE_MINUTES) return 'wait-late';
    if (wait >= WAIT_WARN_MINUTES) return 'wait-warn';
    return 'wait-ok';
  }

  /** Spice is shouted to the pass in words, not degrees, so it reads as text. */
  spiceLabel(spice?: string | null): string {
    return spice ? spice.replace(/_/g, ' ') : '';
  }

  private fail(err: any, fallback: string): void {
    this._snackbar.openSnackBar(err?.error?.message || fallback, 'error');
  }
}