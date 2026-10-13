import { Injectable, signal } from '@angular/core';
import { IDraftReservationData } from '../models/IReservation.model';

@Injectable({
  providedIn: 'root'
})
export class BookingStateService {

  private readonly STORAGE_KEY = 'hms_draft_reservation';
  
  // Signal to drive the UI & Summary Badge reactively
  readonly draftBooking = signal<IDraftReservationData | null>(this.getInitialState());

  private getInitialState(): IDraftReservationData | null {
    const saved = sessionStorage.getItem(this.STORAGE_KEY);
    return saved ? JSON.parse(saved) : null;
  }

  setRoomSelection(data: IDraftReservationData): void {
    this.draftBooking.set(data);
    sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(data));
  }

  // updateGuestInfo(guestId: number, name: string, phone: string): void {
  updateGuestInfo(guestId: number, name: string): void {
    const current = this.draftBooking();
    if (current) {
      // const updated = { ...current, guest_id: guestId, guest_name: name, guest_phone: phone };
      const updated = { ...current, guest_id: guestId, guest_name: name };
      this.draftBooking.set(updated);
      sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(updated));
    }
  }

  clearDraft(): void {
    this.draftBooking.set(null);
    sessionStorage.removeItem(this.STORAGE_KEY);
  }
}
