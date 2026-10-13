import { Injectable } from '@angular/core';
import Swal, { SweetAlertResult, SweetAlertOptions } from 'sweetalert2';

@Injectable({
  providedIn: 'root'
})
export class ConfirmationService {

  confirm(
    title: string = 'Are you sure?',
    message: string = '',
    confirmText: string = 'Yes, proceed'
  ): Promise<SweetAlertResult> {
    
    const options: SweetAlertOptions = {
      title: title,
      text: message,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: confirmText,
      cancelButtonText: 'Cancel',
      //// reverseButtons: true,
      // Sizing/colour live in the global stylesheet under
      // `.swal-container-css` — the popup renders into <body>, outside every
      // component view, so component-scoped styles can never reach it.
      customClass: {
        container: 'swal-container-css',
        popup: 'swal-popup-css',
        title: 'swal-title-css',
        htmlContainer: 'swal-content-css',
        actions: 'swal-actions-css',
        icon: 'swal-icon-css',
        confirmButton: 'swal-btn-confirm-css',
        cancelButton: 'swal-btn-cancel-css'
      }
    };
    return Swal.fire(options);
  }

  confirmDelete(message: string = 'This action cannot be undone!'): Promise<SweetAlertResult> {
    return this.confirm('Delete Confirmation', message, 'Yes, Delete it!');
  }

  /**
   * Confirmation that also collects a mandatory free-text reason.
   *
   * `confirm()` cannot be reused here: it has no input, and the cancel reason is
   * required by the backend rather than optional metadata. Resolves to
   * `{ confirmed, reason }` -- `reason` is only meaningful when confirmed.
   * Resolves (never rejects) on dismiss, so callers just check `confirmed`.
   */
  async confirmWithReason(
    title: string,
    message: string,
    confirmText: string = 'Yes, proceed',
    placeholder: string = 'Enter reason'
  ): Promise<{ confirmed: boolean; reason: string }> {
    const result = await Swal.fire({
      title,
      text: message,
      icon: 'warning',
      input: 'text',
      inputPlaceholder: placeholder,
      inputAttributes: { 'aria-label': placeholder, maxlength: '255' },
      showCancelButton: true,
      confirmButtonText: confirmText,
      cancelButtonText: 'Cancel',
      inputValidator: (value: string) => {
        // mirrors the server's own check, so an empty reason never round-trips
        if (!value || !value.trim()) return 'Please enter a reason';
        return null;
      },
      // same global styling as confirm() -- the popup renders into <body>,
      // outside every component view, so component styles can never reach it.
      // `swal-popup-input-css` widens the popup only for this dialog: the
      // reason field plus its guidance placeholder need more horizontal room
      // than a plain yes/no prompt.
      customClass: {
        container: 'swal-container-css',
        popup: 'swal-popup-css swal-popup-input-css',
        title: 'swal-title-css',
        htmlContainer: 'swal-content-css',
        actions: 'swal-actions-css',
        icon: 'swal-icon-css',
        confirmButton: 'swal-btn-confirm-css',
        cancelButton: 'swal-btn-cancel-css'
      }
    });

    return {
      confirmed: !!result.isConfirmed,
      reason: result.isConfirmed ? String(result.value ?? '').trim() : ''
    };
  }
}
