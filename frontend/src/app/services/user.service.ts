import { HttpClient, HttpHeaders } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { IEntityResponse, IGenericPagination } from '../models/ICommon.model';
import { IUsers } from '../models/IAdmin.model';
import { AppConfig } from '../core/config/config';
@Injectable({
  providedIn: 'root'
})
export class UserService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);
  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  getUsers(data: IGenericPagination): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/user/get`, data);
  }
  insertUpdateUser(reqdata: IUsers): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/user/upsert`, reqdata)
  }

  getUserById(userId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/user/get-by-id?id=${userId}`)
  }

  signup(data: any) {
    return this.http.post(this.baseURL+ "/user/signup", data,{
      headers: new HttpHeaders().set('Content-Type', "application/json")
    })
  }
  verifyUser(token: string): Observable<any> {
    const apiUrl = `${this.baseURL}/user/verifyEmail?token=${token}`;
    return this.http.get(apiUrl);
  }

  verifyTOTP(data: any): Observable<any> {
    // Add the API endpoint for TOTP verification
    return this.http.post(`${this.baseURL}/user/verifyTOTP`, data);
  }
  forgotPassword(data: any) {
    return this.http.post(this.baseURL + "/user/forgotPassword/", data, {
      headers: new HttpHeaders().set('Content-Type', "application/json")
    })
  }

  verifyOTP(data: any): Observable<any> {
    // Add the API endpoint for TOTP verification
    return this.http.post(`${this.baseURL}/user/verifyOTP`, data);
  }
  setPassword(data: any) {
    return this.http.post(this.baseURL + "/user/setPassword", data, {
      headers: new HttpHeaders().set('Content-Type', "application/json")
    })
  }

  checkToken() {
    return this.http.get(this.baseURL + "/user/checkToken")
  }
  changePassword(data: any) {
    return this.http.post(this.baseURL + "/user/changePassword", data,{
      headers: new HttpHeaders().set('Content-Type', "application/json")
    })
  }

  //THIS IS NOT WORKING BECAUSE USER STATUS UPDATES WHEN USER VERIFY EMAIL
  updateUserStatus(data:any) {
    return this.http.patch(this.baseURL + "/user/updateStatus", data, {
      headers: new HttpHeaders().set('Content-Type', "application/json")
    })
  }

}
