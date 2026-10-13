import { Injectable } from '@angular/core';
import {
    HttpInterceptor,
    HttpEvent,
    HttpHandler, 
    HttpRequest, 
    HttpErrorResponse,
    HttpClient
} from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { catchError, filter, switchMap, take } from 'rxjs/operators';
import { Router } from '@angular/router';
import { AppConfig } from '../core/config/config';
import { STORAGE_KEYS } from './config/storage-keys';


@Injectable()
export class HttpIntercept implements HttpInterceptor {

    private isRefreshing = false;
    private refreshTokenSubject: BehaviorSubject<string | null> = new BehaviorSubject<string | null>(null);

    constructor(
        private router: Router,
        private http: HttpClient,
        private config: AppConfig,
    ) {}


    intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {

        const accessToken = sessionStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);

        //// Do NOT attach token for login or public APIs
        const isPublicApi =
            req.url.includes('/auth/login') ||
            req.url.includes('/auth/get-fresh-token') ||
            req.url.includes('/assets/');
        
        let authReq = req;

        if (accessToken && !isPublicApi) {
            authReq = this.addToken(req, accessToken);
        }

        return next.handle(authReq).pipe(
            catchError((error: HttpErrorResponse) => {

                const isAuthOrValidationApi =
                    authReq.url.includes('/auth/verify-email') ||
                    authReq.url.includes('/auth/login') ||
                    authReq.url.includes('/auth/get-fresh-token') ||
                    authReq.url.includes('/auth/reset-password') ||
                    authReq.url.includes('/user-account/update-password') ||
                    authReq.url.includes('/auth/activate-account');
                if (error.status === 401 && !isPublicApi && !isAuthOrValidationApi) {
                    return this.handle401Error(authReq, next);
                }
                
                return throwError(() => error);
            })
        );
    }

    private addToken(req: HttpRequest<any>, token:string): HttpRequest<any> {
        return req.clone({
            setHeaders: {
                Authorization: `Bearer ${token}`
            }
        });
    }

    private handle401Error(
        request: HttpRequest<any>,
        next: HttpHandler
    ): Observable<HttpEvent<any>> {
        if (!this.isRefreshing) {
            this.isRefreshing = true;
            this.refreshTokenSubject.next(null);
            return this.http.post<any>(
                `${this.config.get('BASE_URL')}/api/v1/auth/get-fresh-token`,
                {},
                { withCredentials: true }
            ).pipe(
                //// 1. Handle errors for the REFRESH call specifically
                catchError(() => {
                    this.isRefreshing = false;
                    return this.logout(); //// Refresh failed, log out
                }),
                switchMap((res) => {
                    this.isRefreshing = false;
                    if (res?.status && res?.data?.access_token) {
                        sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, res.data.access_token);
                        localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(res.data));
                        this.refreshTokenSubject.next(res.data.access_token);
                        return next.handle(this.addToken(request, res.data.access_token));
                    }
                    return this.logout();
                })
            );
        }

        //// If refresh already in progress, wait
        return this.refreshTokenSubject.pipe(
            filter(token => token !== null),
            take(1),
            switchMap(token =>
                next.handle(this.addToken(request, token!))
            )
        );
    }

    private logout(): Observable<never> {
        sessionStorage.clear();
        localStorage.clear();
        this.router.navigate(['/auth/login']);
        return throwError(() => new Error('Session expired'));
    }
}
