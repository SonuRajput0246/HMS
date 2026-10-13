import { Component, inject } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { ActivatedRoute, Router } from '@angular/router';
import { ReservationService } from '../../../services/reservation.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { finalize } from 'rxjs/operators';


/**
 * Statuses a booking can still be cancelled from.
 *
 * MUST match CANCELLABLE_STATUSES in
 * HMS_Flask/src/api/services/reservation_service.py. A completed stay cannot be
 * un-stayed, so cancelling one would rewrite the record of what the guest
 * actually consumed.
 */
const CANCELLABLE_STATUSES = ['created', 'reserved', 'checked_in'];


@Component({
  selector: 'app-reservation-details',
  templateUrl: './reservation-details.component.html',
  styleUrl: './reservation-details.component.scss'
})
export class ReservationDetailsComponent {

  private AR = inject(ActivatedRoute);
  private _reservationService = inject(ReservationService);
  private _confirmService = inject(ConfirmationService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);

  navData: INavigationaBar[] = [];
  reservationId: number | null = null;
  reservation: any = null;
  totalNights: number = 0;
  isLoading = false;

  /**
   * Payment figures are derived from the `payments[]` ledger, not from a
   * single-row aggregate. `advance_payment` only ever described the first
   * advance, so a reservation settled in instalments reported one payment and
   * a balance that ignored everything after it.
   *
   * Refunds arrive with a positive amount and an `is_refund` flag, so they are
   * subtracted here rather than carrying a sign of their own.
   */
  private get ledger(): any[] {
    const rows = this.reservation?.payments;
    return Array.isArray(rows) ? rows : [];
  }

  /** Money actually held against the stay, net of refunds. */
  get paidTotal(): number {
    return this.ledger.reduce((sum, p) => {
      const amount = Number(p?.amount) || 0;
      return sum + (p?.is_refund ? -amount : amount);
    }, 0);
  }

  /** Total handed back to the guest. Shown so an over-collection is explicable. */
  get refundTotal(): number {
    return this.ledger.reduce((sum, p) => {
      if (!p?.is_refund) return sum;
      return sum + (Number(p?.amount) || 0);
    }, 0);
  }

  /** True when refunds have pushed the stay into a credit position. */
  get isRefunded(): boolean {
    return this.refundTotal > 0;
  }

  /**
   * Outstanding = total − paid. Clamped at 0 so the tile never shows a
   * negative balance for an over-collected stay; `overCollectedAmount`
   * carries the surplus separately.
   */
  get balanceAmount(): number {
    return Math.max(0, (Number(this.reservation?.total_amount) || 0) - this.paidTotal);
  }

  /** How much more was collected than the stay was worth, when applicable. */
  get overCollectedAmount(): number {
    return Math.max(0, this.paidTotal - (Number(this.reservation?.total_amount) || 0));
  }

  /**
   * A single method only makes sense while one payment exists. With several
   * there is no one answer, so say so rather than picking whichever row
   * happened to sort first.
   */
  get paymentMethodSummary(): string {
    const methods = Array.from(new Set(
      this.ledger
        .map(p => String(p?.payment_method || '').replace(/_/g, ' ').trim())
        .filter(Boolean)
    ));

    if (!methods.length) return 'N/A';
    if (methods.length === 1) return methods[0].toUpperCase();
    return `${methods.length} METHODS`;
  }

  ngOnInit(): void {
    this.initNavigation();
    this.reservationId = Number(this.AR.snapshot.paramMap.get('reservationId'));
    if (this.reservationId) {
      this.loadReservationDetails();
    } else {
      this.onBack();
    }
  }

  initNavigation() {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Reservation Management', isClickable: true, isDashboard: false, redirectValue: '/hms/reservations' },
      { displayValue: 'Reservation Details', isClickable: false, isDashboard: false}
    ]
  }

  loadReservationDetails(): void {
    this.isLoading = true;
    this._reservationService.getReservationById(this.reservationId!)
    .pipe(finalize(() => this.isLoading = false))
    .subscribe({
      next: (res: any) => {
        if (res && res.status) {
          this.reservation = res.data;
          this.calculateNights();
        } else {
          this._snackbar.openSnackBar(res.message || 'Failed to fetch details', 'error');
        }
        this.isLoading = false;
      },
      error: (err: any) => {
        const msg = err?.error?.message || 'An error occurred while fetching reservation details';
          this._snackbar.openSnackBar(msg, 'error');
      }
    });
  }

  calculateNights(): void {
    if (this.reservation?.check_in_date && this.reservation?.check_out_date) {
      const inDate = new Date(this.reservation.check_in_date);
      const outDate = new Date(this.reservation.check_out_date);
      const diffTime = Math.abs(outDate.getTime() - inDate.getTime());
      this.totalNights = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }
  }

  getTotalGuests(): number {
    return (this.reservation?.adults_count || 0) + 
          (this.reservation?.children_count || 0) + 
          (this.reservation?.infants_count || 0);
  }

  getGuestSummary(): string {
    if (!this.reservation) return 'N/A';
    
    const parts: string[] = [];
    const adults = this.reservation.adults_count || 0;
    const children = this.reservation.children_count || 0;
    const infants = this.reservation.infants_count || 0;

    if (adults > 0) parts.push(`${adults} ${adults === 1 ? 'Adult' : 'Adults'}`);
    if (children > 0) parts.push(`${children} ${children === 1 ? 'Child' : 'Children'}`);
    if (infants > 0) parts.push(`${infants} ${infants === 1 ? 'Infant' : 'Infants'}`);

    return parts.length > 0 
      ? `${this.getTotalGuests()} ${this.getTotalGuests() === 1 ? 'Guest' : 'Guests'} (${parts.join(', ')})`
      : 'No guests specified';
  }

  onBack(): void {
    this._router.navigate(['/hms/reservations']);
  }

  onEdit(): void {
    this._router.navigate([`/hms/reservations/edit/${this.reservationId}`]);
  }

  onCheckIn(): void {
    // Call Check-in API
  }

  // ---------------------------------------------------------------
  //  Cancellation
  // ---------------------------------------------------------------

  /** Set while the cancel request is in flight, to disable the button. */
  isCancelling = false;

  /**
   * Whether the cancel button should be enabled.
   *
   * Mirrors the server's CANCELLABLE_STATUSES in reservation_service.py. This
   * has to be duplicated client-side because the button has to render disabled
   * before the operator clicks -- there is no per-request API for "may I cancel
   * this?". The consequence is that the two can drift: if the server rule
   * changes, this list must change with it, and the failure mode is a 422 the
   * operator only sees after clicking. Keeping the values adjacent to this
   * getter is deliberate -- do not move them into a shared constants file.
   */
  get isCancellable(): boolean {
    const status = String(this.reservation?.reservation_status || '').toLowerCase();
    return CANCELLABLE_STATUSES.includes(status);
  }

  onCancel(): void {
    if (!this.isCancellable || this.isCancelling) return;

    const number = this.reservation?.reservation_number || `reservation #${this.reservationId}`;

    // Warn about money before asking for the reason -- the operator may want
    // to handle the advance first, and there is no point collecting a reason
    // for an action they will not take.
    if (this.paidTotal > 0) {
      this._confirmService.confirm(
        'Money collected against this stay',
        `₹${this.paidTotal.toLocaleString('en-IN', { maximumFractionDigits: 0 })} has been `
        + `collected for ${number}. Cancelling does not refund it — record a refund separately. `
        + `Continue anyway?`,
        'Yes, cancel anyway'
      ).then(ok => {
        if (ok.isConfirmed) this.promptCancelReason(number);
      });
      return;
    }

    this.promptCancelReason(number);
  }

  private promptCancelReason(reservationLabel: string): void {
    this._confirmService
      .confirmWithReason(
        'Cancel reservation',
        `Enter the reason for cancelling ${reservationLabel}. This is recorded against the booking.`,
        'Yes, cancel reservation',
        'e.g. Guest cancelled by phone'
      )
      .then(({ confirmed, reason }) => {
        if (!confirmed) return;
        this.submitCancellation(reason);
      });
  }

  private submitCancellation(reason: string): void {
    this.isCancelling = true;
    this._reservationService.cancelReservation(this.reservationId!, reason)
      .pipe(finalize(() => this.isCancelling = false))
      .subscribe({
        next: (res: any) => {
          if (res?.status) {
            // reload rather than patch the row: cancelling changes the status,
            // unlocks/locks buttons, and the response's paid_total can differ
            // from what this page computed before the reload
            this.loadReservationDetails();
            this._snackbar.openSnackBar(res.message || 'Reservation cancelled', 'success');

            if (res.data?.refund_required && Number(res.data?.paid_total) > 0) {
              this._snackbar.openSnackBar(
                `A refund of ₹${Number(res.data.paid_total).toLocaleString('en-IN', { maximumFractionDigits: 0 })} is due on this booking.`,
                'warning'
              );
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to cancel reservation', 'error');
          }
        },
        error: (err: any) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while cancelling the reservation', 'error'
          );
        }
      });
  }
}
