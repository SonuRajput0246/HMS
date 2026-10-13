import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse } from '../models/ICommon.model';
import { Observable } from 'rxjs';
import { IFilterAvailableRooms, IFilterReservations } from '../models/IReservation.model';
@Injectable({
  providedIn: 'root'
})
export class ReservationService {
  private http = inject(HttpClient);
  private config = inject(AppConfig);
  private readonly baseURL: string;
  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }
  getAllReservations(data: IFilterReservations): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/reservation/get`, data);
  }
  getAvailableRooms(data: IFilterAvailableRooms): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/reservation/get-available-rooms`, data);
  }
  insertGuestAndReservation(data:any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/reservation/create-reservation-upsert-guest`, data);
  }
  deleteReservation(reservation_id: number): Observable<IEntityResponse> {
    return this.http.delete(`${this.baseURL}/api/v1/reservation/delete/${reservation_id}`);
  }
  /**
   * Cancel a booking. `cancellation_reason` is mandatory server-side; the
   * acting user is taken from the auth token, never sent from here.
   */
  cancelReservation(reservation_id: number, cancellation_reason: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/reservation/cancel/${reservation_id}`, { cancellation_reason });
  }
  insertPaymentDetails(data: any): Observable<IEntityResponse> {
    console.log('Inserting payment details with data:', data);
    return this.http.post(`${this.baseURL}/api/v1/reservation/payment-details`, data);
  }
  getReservationById(reservation_id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/reservation/get-by-id/${reservation_id}`);
  }
  updateReservation(data: any): Observable<IEntityResponse> {
    return this.http.put(`${this.baseURL}/api/v1/reservation/update`, data);
  }
  updateReservationGuests(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/reservation/update-guests`, data);
  }

}
