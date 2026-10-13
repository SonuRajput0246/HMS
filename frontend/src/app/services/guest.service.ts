import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse, IGenericPagination } from '../models/ICommon.model';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class GuestService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private _baseURL = this.config.get('BASE_URL')

  constructor() {
    this._baseURL = this.config.get('BASE_URL');
  }


  getGuests(data: IGenericPagination): Observable<IEntityResponse>{
    return this.http.post(`${this._baseURL}/api/v1/guest/get-all`, data)
  }

  getGuestById(guestId: number): Observable<IEntityResponse>{
    return this.http.get(`${this._baseURL}/api/v1/guest/get-by-id?id=${guestId}`)
  }

  insertUpdateGuest(data: any): Observable<IEntityResponse>{
    return this.http.post(`${this._baseURL}/api/v1/guest/upsert`, data)
  }
}
