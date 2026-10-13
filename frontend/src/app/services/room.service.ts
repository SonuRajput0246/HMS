import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse } from '../models/ICommon.model';
import { Observable } from 'rxjs';
import { IFilterRooms, IRooms } from '../models/IRoom.model';

@Injectable({
  providedIn: 'root'
})
export class RoomService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  getEnumOptions(enumKey: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/common/get-enum-options`, { enum_key: enumKey });
  }

  getAllRooms(data: IFilterRooms): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/room/get-all`, data);
  }

  getRoomById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/room/get-by-id?id=${id}`)
  }

  getRoomTypes(): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/room/get-types`);
  }

  insertUpdateRoom(reqdata: IRooms): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/room/upsert`, reqdata)
  }
}
