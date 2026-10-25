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
import { PLATFORM_ACCESS_TOKEN_KEY, PLATFORM_PROFILE_KEY } from './config/platform-storage';
import { InstanceService } from './config/instance.service';
import { TENANT_HEADER } from './config/tenant';

/**
 * The API namespace that carries the platform session.
 *
 * A platform caller belongs to no hotel, so every call under it is
 * authenticated with the platform token and travels with no tenant header.
 * Matching on the path rather than on the current host is deliberate: it holds
 * on the console host *and* anywhere else a stray platform call is made, so a
 * mis-routed request is refused by the server rather than being sent with a
 * hotel token attached.
 */
const PLATFORM_API = '/api/v1/platform';


@Injectable()
export class HttpIntercept implements HttpInterceptor {

    private isRefreshing = false;
    private refreshTokenSubject: BehaviorSubject<string | null> = new BehaviorSubject<string | null>(null);

    constructor(
        private router: Router,
        private http: HttpClient,
        private config: AppConfig,
        private instance: InstanceService,
    ) {}


    intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {

        const isPlatformApi = req.url.includes(`${PLATFORM_API}/`);

        //// The console and the hotel app share this browser, so the two
        //// sessions are told apart by URL: a call to the platform API carries
        //// the platform token, everything else carries the hotel token.
        const accessToken = isPlatformApi
            ? sessionStorage.getItem(PLATFORM_ACCESS_TOKEN_KEY)
            : sessionStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);

        //// Do NOT attach token for login or public APIs
        const isPublicApi =
            req.url.includes('/auth/login') ||
            req.url.includes('/auth/get-fresh-token') ||
            req.url.includes('/assets/');

        //// A platform caller has no hotel, so it must not send a slug --
        //// doing so would make the backend read it as a hotel request.
        let authReq = isPlatformApi ? req : this.addTenant(req);

        if (accessToken && !isPublicApi) {
            authReq = this.addToken(authReq, accessToken);
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
                    //// The hotel refresh mints a hotel token, which the
                    //// platform API rejects; a platform 401 is terminal.
                    if (isPlatformApi) {
                        return this.handlePlatform401();
                    }
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

    /**
     * Name the hotel on every request, including the ones that run before login.
     *
     * The API cannot see which hotel it is serving when the app and the API are
     * on different origins -- the development setup, where the browser talks to
     * `acme.localhost:4200` and the API answers on `localhost:5000` -- so the
     * tenant travels in a header. Requests for the app's own static assets are
     * left alone: they never reach the API and a custom header buys nothing.
     *
     * An explicit header wins, so a caller (or a test) can override it.
     */
    private addTenant(req: HttpRequest<any>): HttpRequest<any> {
        const slug = this.instance.slug;
        const isStaticAsset = /(^|\/)assets\//.test(req.url);
        if (!slug || isStaticAsset || req.headers.has(TENANT_HEADER)) {
            return req;
        }
        return req.clone({
            setHeaders: {
                [TENANT_HEADER]: slug
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

    /**
     * A platform token cannot be refreshed: `/auth/get-fresh-token` is the hotel
     * endpoint and signs a hotel token, which the platform API refuses at the
     * signature check. So a 401 here clears the platform session and returns to
     * the console's sign-in.
     *
     * Only the platform keys are removed. `sessionStorage.clear()` would sign the
     * operator out of every hotel in other tabs too, which is not what "your
     * console session expired" means.
     */
    private handlePlatform401(): Observable<never> {
        sessionStorage.removeItem(PLATFORM_ACCESS_TOKEN_KEY);
        localStorage.removeItem(PLATFORM_PROFILE_KEY);
        this.router.navigate(['/login'], { replaceUrl: true });
        return throwError(() => new Error('Platform session expired'));
    }
}
