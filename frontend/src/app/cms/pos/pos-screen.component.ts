import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin, interval } from 'rxjs';
import { finalize, switchMap } from 'rxjs/operators';

import {
  IBill,
  IFloorTable,
  IFloorView,
  IMenu,
  IMenuSection,
  IOrderDetail,
  IOrderItem,
  IPosSummary,
  IRecipe,
  PAYMENT_METHOD_LABELS,
  PaymentMethod,
  PREP_STATUS_LABELS,
  PrepStatus,
  TABLE_STATUS_LABELS,
  TableStatus,
  toAmount
} from '../../models/ICms.model';
import { CmsFloorService } from '../../services/cms/floor.service';
import { CmsCustomerService } from '../../services/cms/customer.service';
import { CmsOrderService } from '../../services/cms/order.service';
import { CmsRecipeService } from '../../services/cms/recipe.service';
import { ConfirmationService } from '../../services/confirmation.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';

/** How often the idle floor re-reads itself. */
const FLOOR_POLL_MS = 15000;

/**
 * The cashier's screen.
 *
 * Everything on this page answers one question -- "which bill am I ringing up?"
 * -- so the component holds exactly one piece of truth, the currently open
 * `order`, and refuses to poll the floor while it is set. A background refresh
 * that reshuffles table states under a half-typed transaction is how a drink
 * gets rung against the wrong table.
 *
 * Deliberately one route with no dialogs: a mat-dialog renders in an overlay,
 * so a payment popup would sit above the cart with the floor still clickable
 * behind it. Payment is an inline panel instead -- the cashier never loses the
 * bill they are holding.
 */
@Component({
  selector: 'app-pos-screen',
  templateUrl: './pos-screen.component.html',
  styleUrl: './pos-screen.component.scss'
})
export class PosScreenComponent implements OnInit {

  //// Inject Services
  private _orderService = inject(CmsOrderService);
  // The till genuinely needs both: the floor for tables, the customer service
// to identify who is paying. Previously one service covered both, which meant
// every other customer screen also depended on a service named after the
// floor.
private _floorService = inject(CmsFloorService);
private _customerService = inject(CmsCustomerService);
  private _recipeService = inject(CmsRecipeService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirm = inject(ConfirmationService);
  private _destroyRef = inject(DestroyRef);

  //// Constants
  readonly TABLE_STATUS_LABELS = TABLE_STATUS_LABELS;
  readonly PREP_STATUS_LABELS = PREP_STATUS_LABELS;

  /**
   * The till takes these four. `split` is deliberately absent: a split bill is
   * several payments under one shared group id, and this screen settles in a
   * single closeOrder call, so offering the chip would promise something the
   * flow cannot deliver.
   */
  readonly PAYMENT_METHODS: PaymentMethod[] = ['cash', 'card', 'upi', 'wallet'];

  //// State Properties
  /** Blocking overlay. Raised only for loads the cashier must WAIT for. */
  isPageLoad = false;
  /** A background poll is in flight. Never raises the blocking overlay. */
  isPolling = false;
  /** A cart write is in flight; greys out the row that triggered it. */
  isWorking = false;

  floorView: IFloorView | null = null;
  summary: IPosSummary | null = null;
  menu: IMenu | null = null;
  order: IOrderDetail | null = null;
  bill: IBill | null = null;

  /** Section key of the recipe grid. 'all' keeps every dish one tap away. */
  activeSectionKey = 'all';

  //// Customer lookup state
  lookupPhone = '';
  lookupName = '';
  /** Appears only once a phone lookup misses, so a returning guest types once. */
  needsCustomerName = false;

  //// Payment panel state
  showPayment = false;
  payMethod: PaymentMethod = 'cash';
  /** Pre-filled with the due; the wire amount is always the server's own due. */
  payAmount = '';
  /** Cash only. Drives the change figure; never sent to the server. */
  cashTendered = '';

  ngOnInit(): void {
    this.loadInitial();

    /**
     * Floor + summary polling. The guard is the entire point of this
     * subscription: while a bill is open the floor is frozen and the cashier
     * gets an explicit Refresh button instead, because a table changing status
     * mid-transaction looks exactly like a bug and is impossible to explain.
     */
    interval(FLOOR_POLL_MS)
      .pipe(
        switchMap(() => (this.order || this.isPolling) ? [] : [true]),
        takeUntilDestroyed(this._destroyRef)
      )
      .subscribe(() => this.pollFloor());
  }

  //// ------------------------------------------------------------------
  ////  Derived read models -- money only ever leaves here via toAmount()
  //// ------------------------------------------------------------------

  get zones() {
    return this.floorView?.zones ?? [];
  }

  get sections(): IMenuSection[] {
    return this.menu?.sections ?? [];
  }

  /** Recipes for the active section. 'all' is a fallback, not a real section. */
  get visibleRecipes(): IRecipe[] {
    if (this.activeSectionKey === 'all') {
      return this.sections.flatMap(s => s.recipes);
    }
    const section = this.sections.find(s => this.sectionKey(s) === this.activeSectionKey);
    return section?.recipes ?? [];
  }

  get activeSectionTitle(): string {
    if (this.activeSectionKey === 'all') return 'Full menu';
    const section = this.sections.find(s => this.sectionKey(s) === this.activeSectionKey);
    return section?.category_display_name || section?.category_name || 'Menu';
  }

  /** Cart lines come from the order, never from a locally patched copy. */
  get cartItems(): IOrderItem[] {
    return this.order?.items ?? [];
  }

  /**
   * The bill recomputes totals from the live lines; the order header is a
   * cached copy of the same maths. Preferring the bill means the number the
   * cashier reads aloud is the one the server would charge.
   */
  private totals(): IBill['totals'] {
    if (this.bill) return this.bill.totals;
    return {
      item_subtotal: this.order?.subtotal ?? '0',
      tax_amount: this.order?.tax_amount ?? '0',
      discount_amount: this.order?.discount_amount ?? '0',
      total_amount: this.order?.total_amount ?? '0',
      paid_amount: this.order?.paid_amount ?? '0',
      due_amount: this.order?.due_amount ?? '0'
    };
  }

  get subtotal(): number { return toAmount(this.totals().item_subtotal); }
  get tax(): number { return toAmount(this.totals().tax_amount); }
  get discount(): number { return toAmount(this.totals().discount_amount); }
  get total(): number { return toAmount(this.totals().total_amount); }
  get paid(): number { return toAmount(this.totals().paid_amount); }
  get dueAmount(): number { return toAmount(this.totals().due_amount); }

  /** Cash handed over, as a number. Parsed once here so the template stays arithmetic-free. */
  get tenderedAmount(): number {
    return toAmount(this.cashTendered);
  }

  /** Change to hand back. Floored at zero -- a short tender is a problem, not change. */
  get changeDue(): number {
    return Math.max(0, this.tenderedAmount - this.dueAmount);
  }

  get kitchenOutstanding(): number {
    return this.bill?.kitchen_outstanding ?? 0;
  }

  /** Sum of the line quantities, so the header can say "6 items" without paging. */
  get cartCount(): number {
    return this.cartItems.reduce((sum, line) => sum + toAmount(line.quantity), 0);
  }

  //// ------------------------------------------------------------------
  ////  Loading
  //// ------------------------------------------------------------------

  /**
   * One blocking paint from three reads. They are independent and each is
   * needed before the screen means anything, so a single forkJoin beats three
   * sequential round trips on a café wifi.
   */
  private loadInitial(): void {
    this.isPageLoad = true;
    forkJoin({
      floor: this._floorService.getFloorView(),
      summary: this._orderService.getSummary(true),
      menu: this._recipeService.getMenu({ include_unavailable: false })
    })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: ({ floor, summary, menu }) => {
          // A 200 with status:false is still a failure the cashier must see.
          if (!floor?.status || !summary?.status || !menu?.status) {
            this._snackbar.openSnackBar(
              floor?.message || summary?.message || menu?.message || 'Failed to load the till',
              'error'
            );
            return;
          }
          this.floorView = floor.data as IFloorView;
          this.summary = summary.data as IPosSummary;
          this.menu = menu.data as IMenu;
        },
        error: (err) => this.fail(err, 'Could not load the till')
      });
  }

  /**
   * Background refresh. Never raises the blocking overlay: the cashier may be
   * mid-sentence with a guest, and a full-page spinner over a background read
   * lies about what the screen is doing.
   */
  pollFloor(): void {
    if (this.order) return;
    this.isPolling = true;
    forkJoin({
      floor: this._floorService.getFloorView(),
      summary: this._orderService.getSummary(true)
    })
      .pipe(finalize(() => this.isPolling = false))
      .subscribe({
        next: ({ floor, summary }) => {
          if (floor?.status) this.floorView = floor.data as IFloorView;
          if (summary?.status) this.summary = summary.data as IPosSummary;
        },
        // A failed background poll is not worth a snackbar -- the next tick in
        // 15s retries, and a toast every 15s only teaches staff to ignore it.
        error: () => { /* retried on the next tick */ }
      });
  }

  /** The manual escape hatch shown whenever polling is suspended. */
  refreshNow(): void {
    this.pollFloor();
  }

  //// ------------------------------------------------------------------
  ////  Floor interaction
  //// ------------------------------------------------------------------

  onTableTap(table: IFloorTable): void {
    const tableId = table.id;
    if (tableId === undefined || tableId === null) return;

    const status = table.status as TableStatus;

    // Cleaning and maintenance are housekeeping states, not seating states.
    // Saying so plainly beats letting the server reject it with the same words.
    if (status === 'cleaning' || status === 'maintenance') {
      this._snackbar.openSnackBar(
        `Table ${table.table_number ?? ''} is ${this.tableLabel(status).toLowerCase()} and cannot be seated yet.`,
        'warn'
      );
      return;
    }

    if (status === 'occupied') {
      this.openActiveOrderFor(tableId, table.table_number ?? '');
      return;
    }

    // available / reserved -- seat them.
    this.isPageLoad = true;
    this._orderService.createOrder({ reference_type: 'table', reference_id: tableId })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.adoptOrder(res.data as IOrderDetail);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not open the table', 'error');
          }
        },
        error: (err) => {
          /**
           * 409 + existing_order_id is not a failure: it means this table
           * already has a live bill -- another waiter, or another till. The
           * guest is already seated, so open THAT tab rather than shouting an
           * error at a cashier who did nothing wrong.
           */
          const existingId = err?.error?.data?.existing_order_id;
          if (err?.status === 409 && existingId) {
            this.loadOrder(existingId);
            return;
          }
          this.fail(err, 'Could not open the table');
        }
      });
  }

  private openActiveOrderFor(tableId: number, tableNumber: string): void {
    this.isPageLoad = true;
    this._orderService.getActiveOrderByTable(tableId)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.adoptOrder(res.data as IOrderDetail);
          } else {
            this._snackbar.openSnackBar(res?.message || `No open order on table ${tableNumber}`, 'warn');
          }
        },
        // A 404 here is a race, not a crash: the bill was settled between the
        // floor render and the tap.
        error: (err) => this.fail(err, `Could not open table ${tableNumber}`)
      });
  }

  //// ------------------------------------------------------------------
  ////  Walk-in / customer order
  //// ------------------------------------------------------------------

  startWalkin(): void {
    this.isPageLoad = true;
    this._orderService.createOrder({ reference_type: 'walkin' })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.adoptOrder(res.data as IOrderDetail);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not open a walk-in bill', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not open a walk-in bill')
      });
  }

  /**
   * Phone-first guest capture.
   *
   * The till knows guests by phone, so the box asks for that one thing first.
   * A miss is not an error at a café counter, it just means the name is needed
   * too -- so the second field appears instead of the flow stopping.
   */
  onLookupCustomer(): void {
    const phone = (this.lookupPhone ?? '').trim();
    if (!phone) {
      this._snackbar.openSnackBar('Enter the guest phone number first', 'warn');
      return;
    }

    this.isPageLoad = true;
    this._customerService.lookupByPhone(phone)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.openCustomerOrder(res.data?.id);
          } else {
            this.needsCustomerName = true;
          }
        },
        error: (err) => {
          // 404 is this endpoint's "not a known guest" answer, not a fault.
          if (err?.status === 404) {
            this.needsCustomerName = true;
            return;
          }
          this.fail(err, 'Customer lookup failed');
        }
      });
  }

  /** Saves the guest record first, then opens their bill. */
  onCreateCustomerOrder(): void {
    const phone = (this.lookupPhone ?? '').trim();
    const name = (this.lookupName ?? '').trim();

    if (!phone) {
      this._snackbar.openSnackBar('Enter the guest phone number first', 'warn');
      return;
    }
    if (!name) {
      this._snackbar.openSnackBar('Enter the guest name first', 'warn');
      return;
    }

    this.isPageLoad = true;
    /**
     * quickCreateCustomer returns the EXISTING customer for a known phone
     * instead of failing, so "found" and "created" are the same outcome here
     * and there is only one branch to get wrong.
     */
    this._customerService.quickCreateCustomer({ name, phone })
      .pipe(
        switchMap((res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Could not save the guest', 'error');
            return [];
          }
          return [res.data?.id as number];
        }),
        finalize(() => this.isPageLoad = false)
      )
      .subscribe({
        next: (customerId) => { if (customerId) this.openCustomerOrder(customerId); },
        error: (err) => this.fail(err, 'Could not save the guest')
      });
  }

  private openCustomerOrder(customerId?: number): void {
    if (!customerId) {
      this._snackbar.openSnackBar('Could not identify the guest', 'error');
      return;
    }

    this.isPageLoad = true;
    this._orderService.createOrder({ reference_type: 'customer', reference_id: customerId })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.adoptOrder(res.data as IOrderDetail);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not open the guest bill', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not open the guest bill')
      });
  }

  //// ------------------------------------------------------------------
  ////  Order lifecycle
  //// ------------------------------------------------------------------

  /**
   * A create / active-order response already carries the full detail payload,
   * so adopting it costs no extra round trip. The bill is fetched alongside it
   * only because `kitchen_outstanding` lives there and nowhere else.
   */
  private adoptOrder(detail: IOrderDetail): void {
    this.order = detail;
    this.resetPaymentPanel();
    if (detail?.id) this.loadBill(detail.id);
  }

  private loadOrder(orderId: number): void {
    this.isPageLoad = true;
    this._orderService.getOrderById(orderId)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.order = res.data as IOrderDetail;
            this.resetPaymentPanel();
            this.loadBill(orderId);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not load that bill', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not load that bill')
      });
  }

  /**
   * Re-reads both documents after any cart write.
   *
   * The write endpoints deliberately return only `{item_id, subtotal,
   * total_amount}` -- an acknowledgement, not the new state. Patching the
   * local copy from that would mean re-deriving tax and payment status on the
   * client, and the bill recomputes from the live lines regardless. Two reads
   * cost less than being wrong about money.
   */
  private reloadOrder(): void {
    const orderId = this.order?.id;
    if (!orderId) return;

    this.isWorking = true;
    forkJoin({
      order: this._orderService.getOrderById(orderId),
      bill: this._orderService.getBill(orderId)
    })
      .pipe(finalize(() => this.isWorking = false))
      .subscribe({
        next: ({ order, bill }) => {
          if (order?.status) this.order = order.data as IOrderDetail;
          if (bill?.status) this.bill = bill.data as IBill;
        },
        error: (err) => this.fail(err, 'Could not refresh the bill')
      });
  }

  private loadBill(orderId: number): void {
    this._orderService.getBill(orderId)
      .subscribe({
        next: (res) => { if (res?.status) this.bill = res.data as IBill; },
        error: (err) => this.fail(err, 'Could not load the bill')
      });
  }

  /** Back to the floor. Reachable once the bill is settled or handed back. */
  closeOrderPanel(): void {
    this.order = null;
    this.bill = null;
    this.resetPaymentPanel();
    this.pollFloor();
  }

  //// ------------------------------------------------------------------
  ////  Menu picker
  //// ------------------------------------------------------------------

  onSelectSection(section: IMenuSection): void {
    this.activeSectionKey = this.sectionKey(section);
  }

  showAllSections(): void {
    this.activeSectionKey = 'all';
  }

  onAddRecipe(recipe: IRecipe): void {
    const orderId = this.order?.id;
    const recipeId = recipe.id;

    if (!orderId || recipeId === undefined) return;

    this.isWorking = true;
    // Quantity 1: the tile is tap-to-add, and deliberate multiples belong on
    // the cart line's stepper where the running count is visible.
    this._orderService.addItem(orderId, { recipe_id: recipeId, quantity: 1 })
      .pipe(finalize(() => this.isWorking = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.reloadOrder();
          } else {
            this._snackbar.openSnackBar(res?.message || `Could not add ${recipe.name ?? 'the item'}`, 'error');
          }
        },
        error: (err) => {
          this.fail(err, `Could not add ${recipe.name ?? 'the item'}`);
          // A 409 on add is usually "this dish was just 86'd". Re-reading the
          // menu makes the tile disappear instead of leaving a dead button
          // under the cashier's finger.
          this.refreshMenu();
        }
      });
  }

  /** A dish can be 86'd between the menu load and the tap; keep the grid honest. */
  private refreshMenu(): void {
    this._recipeService.getMenu({ include_unavailable: false })
      .subscribe({
        next: (res) => { if (res?.status) this.menu = res.data as IMenu; },
        error: () => { /* the grid keeps its last good render */ }
      });
  }

  //// ------------------------------------------------------------------
  ////  Cart
  //// ------------------------------------------------------------------

  /**
   * The DB carries `CHECK (quantity > 0)` and the API validates a minimum of
   * 0.001, so the stepper bottoms out at 1 and removal is an explicit,
   * reasoned void rather than a decrement to zero.
   */
  onStepQuantity(item: IOrderItem, delta: number): void {
    const orderId = this.order?.id;
    const itemId = item.id;
    const next = toAmount(item.quantity) + delta;

    if (!orderId || itemId === undefined) return;
    if (next < 1) return;

    // The server refuses to re-quantify a plated line, so say why here rather
    // than letting the cashier discover it through a 409 toast.
    if (item.prep_status === 'ready') {
      this._snackbar.openSnackBar('The kitchen has already plated this one', 'warn');
      return;
    }

    this.isWorking = true;
    this._orderService.updateItemQuantity(orderId, itemId, next)
      .pipe(finalize(() => this.isWorking = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.reloadOrder();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not change the quantity', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not change the quantity')
      });
  }

  /**
   * Removing a line IS a void.
   *
   * The order API has no un-audited delete: `voidItem` is the only removal
   * primitive, it soft-deletes the row so the line survives for the loss
   * report, and it demands a reason because that report groups by one. So
   * there is deliberately ONE removal control per line rather than a "void"
   * and a "delete" that would post the same call twice.
   */
  async onRemoveLine(item: IOrderItem): Promise<void> {
    const orderId = this.order?.id;
    const itemId = item.id;

    if (!orderId || itemId === undefined) return;

    if (item.prep_status === 'ready') {
      this._snackbar.openSnackBar('The kitchen has already plated this one -- it cannot be removed', 'warn');
      return;
    }

    const answer = await this._confirm.confirmWithReason(
      'Remove from bill',
      `Remove "${item.item_name ?? 'this item'}" from the bill? It is recorded against your name.`,
      'Yes, remove it',
      'Reason for removing'
    );
    if (!answer.confirmed) return;

    this.isWorking = true;
    this._orderService.voidItem(orderId, itemId, answer.reason)
      .pipe(finalize(() => this.isWorking = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(`${item.item_name ?? 'Item'} removed`, 'success');
            this.reloadOrder();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not remove the item', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not remove the item')
      });
  }

  //// ------------------------------------------------------------------
  ////  Payment
  //// ------------------------------------------------------------------

  openPayment(): void {
    this.showPayment = true;
    this.payAmount = this.dueAmount.toFixed(2);
    this.cashTendered = '';
  }

  cancelPayment(): void {
    this.showPayment = false;
  }

  selectMethod(method: PaymentMethod): void {
    this.payMethod = method;
  }

  methodLabel(method: PaymentMethod): string {
    return PAYMENT_METHOD_LABELS[method] ?? method;
  }

  /** Material icon per method, so the chip reads without the text at a glance. */
  methodIcon(method: PaymentMethod): string {
    switch (method) {
      case 'cash': return 'payments';
      case 'card': return 'credit_card';
      case 'upi': return 'qr_code';
      case 'wallet': return 'account_balance_wallet';
      default: return 'account_balance';
    }
  }

  /**
   * Settle and close in one call.
   *
   * `complete_payment` makes the server take `order.due_amount()` itself, so
   * the amount on screen is a confirmation for the cashier rather than the wire
   * value -- there is deliberately no path through this method that can send
   * an overpayment, which is exactly what the API rejects and what the audit
   * trail would show.
   */
  async settleAndClose(): Promise<void> {
    const orderId = this.order?.id;
    if (!orderId) return;

    // A typed amount BELOW the due would silently collect less than the panel
    // says it is settling, so refuse rather than quietly charging the full due.
    if (toAmount(this.payAmount) < this.dueAmount) {
      this._snackbar.openSnackBar(
        `Amount must be at least the due of ${this.dueAmount.toFixed(2)}`,
        'warn'
      );
      return;
    }

    // Food still on the pass: closing a takeaway early bills a guest for a
    // plate that has not left the kitchen, and no amount of "I know what I'm
    // doing" makes that recoverable.
    if (this.kitchenOutstanding > 0) {
      const answer = await this._confirm.confirm(
        'Food is still cooking',
        `${this.kitchenOutstanding} item(s) have not been plated yet. Closing now settles the bill before the food goes out.`,
        'Close anyway'
      );
      if (!answer.isConfirmed) return;
    }

    const change = this.payMethod === 'cash' ? this.changeDue : 0;

    this.isWorking = true;
    this._orderService.closeOrder(orderId, {
      complete_payment: true,
      payment_method: this.payMethod
    })
      .pipe(finalize(() => this.isWorking = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            const changeText = change > 0 ? ` — change to return ₹${change.toFixed(2)}` : '';
            this._snackbar.openSnackBar(`Bill settled${changeText}`, 'success');
            this.order = null;
            this.bill = null;
            this.resetPaymentPanel();
            this.pollFloor();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Could not settle the bill', 'error');
          }
        },
        error: (err) => this.fail(err, 'Could not settle the bill')
      });
  }

  private resetPaymentPanel(): void {
    this.showPayment = false;
    this.payMethod = 'cash';
    this.payAmount = '';
    this.cashTendered = '';
  }

  //// ------------------------------------------------------------------
  ////  Template helpers
  //// ------------------------------------------------------------------

  /**
   * category_id is nullable -- the server buckets recipes orphaned from their
   * category into an "Uncategorised" section with a null id -- so sections
   * cannot be keyed by a number that is not always there.
   */
  sectionKey(section: IMenuSection): string {
    return (section.category_id === null || section.category_id === undefined)
      ? 'none'
      : String(section.category_id);
  }

  tableLabel(status?: TableStatus): string {
    return status ? (TABLE_STATUS_LABELS[status] ?? status) : 'Unknown';
  }

  prepLabel(status?: PrepStatus): string {
    return status ? (PREP_STATUS_LABELS[status] ?? status) : 'Unknown';
  }

  private fail(err: any, fallback: string): void {
    this._snackbar.openSnackBar(err?.error?.message || fallback, 'error');
  }
}