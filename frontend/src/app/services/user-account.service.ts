import { inject, Injectable } from '@angular/core';
import { IEntityResponse } from '../models/ICommon.model';
import { HttpClient } from '@angular/common/http';
import { AppConfig } from '../core/config/config';
import { BehaviorSubject, Observable } from 'rxjs';
import { IChangePassword, IUserProfile } from '../models/IAuth.model';
import { STORAGE_KEYS } from '../core/config/storage-keys';

@Injectable({
  providedIn: 'root'
})
export class UserAccountService {

  //// Use 'inject' for a more modern, cleaner approach
  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;
  private userSubject = new BehaviorSubject<IUserProfile | null>(null);

  //// Expose as Observable to prevent external components from calling .next()
  user$ = this.userSubject.asObservable();

  constructor() {
    this.baseURL = this.config.get('BASE_URL');

    //// Initialize user from storage
    const user = localStorage.getItem(STORAGE_KEYS.USER_DATA);
    if (user) {
      try {
        this.userSubject.next(JSON.parse(user));
      } catch (e) {
        console.error('Error parsing user data from localStorage:', e);
      }
    }
  }

  updateUserProfile(reqData: IUserProfile): Observable<IEntityResponse> {
    //// Standard: No map(data => data) or catchError(of)
    //// Let the component or an interceptor handle the error
    return this.http.put(`${this.baseURL}/api/v1/user-account/update-profile`, reqData)
  }

  setUser(user: IUserProfile) {
    this.userSubject.next(user);
  }


  changePassword(reqData: IChangePassword): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(`${this.baseURL}/api/v1/user-account/update-password`, reqData)
  }

  deactivateAccount(reqData: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/user-account/deactivate`,
      reqData,
      { withCredentials: true }
    );
  }

  deleteAccount(reqData: any): Observable<IEntityResponse> {
    return this.http.post<IEntityResponse>(
      `${this.baseURL}/api/v1/user-account/delete`, 
      reqData, 
      { withCredentials: true }
    );
  }

}