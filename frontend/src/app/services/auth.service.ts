import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AppConfig } from '../core/config/config';
import { IAuthRequest } from '../models/IAuth.model';
import { Observable } from 'rxjs';
import { IEntityResponse } from '../models/ICommon.model';

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  signUp(signUpObj: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/auth/register`, signUpObj)
  }

  login(authObj: IAuthRequest): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/auth/login`,
      authObj,
      { withCredentials: true }
    )
  }

  verifyTotpLogin(payload: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/auth/login/verify-totp`, 
      payload,
      { withCredentials: true }
    );
  }

  sendOtp(email: string, type: string): Observable<IEntityResponse> {
    console.log('sendOtp', email, type);
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/auth/send-otp`, { 'email': email, 'otp_type': type})
  }

  activateAccount(payload: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/auth/activate-account`,
      payload,
      { withCredentials: true }
    )
  }

  verifyEmail(payload: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/auth/verify-email`,
      payload,
      { withCredentials: true }
    )
  }


  logout(): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/auth/logout`,
      {},
      { withCredentials: true }
    )
  }

  resetPassword(reqData: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/auth/reset-password`, reqData)
  }

  initiateEnableMfa(user_id: number): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/api/v1/auth/setup-mfa/${user_id}`);
  }

  verifyOrEnableMfa(payload: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/auth/setup-mfa/verify-totp`, payload);
  }

  disableMfa(user_id: number): Observable<IEntityResponse> {
    return this.http.get<IEntityResponse>(`${this.baseURL}/api/v1/auth/disable-mfa/${user_id}`);
  }
  

}
