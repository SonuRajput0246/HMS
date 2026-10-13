import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse, IGenericPagination } from '../models/ICommon.model';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class InventoryService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;
  
  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }


  getCategories(data: IGenericPagination): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/inventory/get-categories`, data);
  }

  insertUpdateCategory(reqdata: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/inventory/upsert-category`, reqdata);
  }

  getCategoryById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/inventory/get-category-by-id?id=${id}`);
  }

  getInventories(data: IGenericPagination): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/inventory/get`, data);
  }

  getInventoryUnits(): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/inventory/get-units`);
  }

  insertUpdateInventory(reqdata: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/inventory/upsert`, reqdata);
  }

  getInventoryById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/inventory/get-by-id?id=${id}`);
  }
}
