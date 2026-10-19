import {
  HttpEvent,
  HttpHandler,
  HttpHeaders,
  HttpRequest,
} from '@angular/common/http';
import { Observable, of } from 'rxjs';

import { AppConfig } from './config/config';
import { InstanceService } from './config/instance.service';
import {
  PLATFORM_ACCESS_TOKEN_KEY,
  PLATFORM_PROFILE_KEY,
} from './config/platform-storage';
import { STORAGE_KEYS } from './config/storage-keys';
import { TENANT_HEADER } from './config/tenant';
import { HttpIntercept } from './http-interceptor';

/**
 * The interceptor is the only place the tenant reaches the wire, so these are
 * the tests that prove the app can talk to a tenant-scoped API at all.
 *
 * The interceptor is built directly rather than through TestBed: it has four
 * collaborators, only one of which carries state that matters here, and the
 * request the next handler receives is the entire subject.
 */
describe('HttpIntercept tenant header', () => {

  const BASE_URL = 'http://localhost:5000';
  const PLATFORM_BASE = `${BASE_URL}/api/v1/platform`;

  function makeInterceptor(slug: string | null): HttpIntercept {
    const config = new AppConfig();
    config.set('BASE_URL', BASE_URL);
    return new HttpIntercept(
      {} as any,                              // Router, only used on the 401 path
      {} as any,                              // HttpClient, only used on the 401 path
      config,
      { slug } as unknown as InstanceService,
    );
  }

  /** Runs one request through the interceptor and returns what `next` saw. */
  function run(url: string, slug: string | null, token?: string): HttpRequest<any> {
    if (token === undefined) {
      sessionStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    } else {
      sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);
    }

    let seen: HttpRequest<any> | undefined;
    const next: HttpHandler = {
      handle(req: HttpRequest<any>): Observable<HttpEvent<any>> {
        seen = req;
        return of({ type: 0 } as any);
      },
    };

    makeInterceptor(slug).intercept(new HttpRequest('GET', url), next).subscribe();
    return seen!;
  }

  /**
   * Runs a request and returns what `next` saw, with a chosen token in each
   * storage slot. Separate from `run` because the platform case needs both keys
   * populated at once to prove which one is sent.
   */
  function runWithBothTokens(
    url: string,
    slug: string | null,
    hotelToken: string | null,
    platformToken: string | null,
  ): HttpRequest<any> {
    if (hotelToken === null) {
      sessionStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    } else {
      sessionStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, hotelToken);
    }
    if (platformToken === null) {
      sessionStorage.removeItem(PLATFORM_ACCESS_TOKEN_KEY);
    } else {
      sessionStorage.setItem(PLATFORM_ACCESS_TOKEN_KEY, platformToken);
    }

    let seen: HttpRequest<any> | undefined;
    const next: HttpHandler = {
      handle(req: HttpRequest<any>): Observable<HttpEvent<any>> {
        seen = req;
        return of({ type: 0 } as any);
      },
    };

    makeInterceptor(slug).intercept(new HttpRequest('GET', url), next).subscribe();
    return seen!;
  }

  afterEach(() => {
    sessionStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    sessionStorage.removeItem(PLATFORM_ACCESS_TOKEN_KEY);
    localStorage.removeItem(PLATFORM_PROFILE_KEY);
  });

  it('names the hotel on an API call', () => {
    expect(run(`${BASE_URL}/api/v1/common/tenant-info`, 'acme').headers.get(TENANT_HEADER))
      .toBe('acme');
  });

  it('names the hotel before login, when no token exists yet', () => {
    const req = run(`${BASE_URL}/api/v1/auth/login`, 'acme');
    expect(req.headers.get(TENANT_HEADER)).toBe('acme');
    expect(req.headers.has('Authorization')).toBe(false);
  });

  it('sends nothing when the host names no hotel', () => {
    expect(run(`${BASE_URL}/api/v1/auth/login`, null).headers.has(TENANT_HEADER))
      .toBe(false);
  });

  it('leaves static assets alone', () => {
    expect(run('assets/config.json', 'acme').headers.has(TENANT_HEADER))
      .toBe(false);
  });

  it('keeps the token and the tenant on the same request', () => {
    const req = run(`${BASE_URL}/api/v1/user/list`, 'acme', 'a-token');
    expect(req.headers.get(TENANT_HEADER)).toBe('acme');
    expect(req.headers.get('Authorization')).toBe('Bearer a-token');
  });

  it('does not overwrite an explicit tenant header', () => {
    let seen: HttpRequest<any> | undefined;
    const next: HttpHandler = {
      handle(req: HttpRequest<any>): Observable<HttpEvent<any>> {
        seen = req;
        return of({ type: 0 } as any);
      },
    };
    const explicit = new HttpRequest('GET', `${BASE_URL}/api/v1/x`, null, {
      headers: new HttpHeaders({ [TENANT_HEADER]: 'globex' }),
    });

    makeInterceptor('acme').intercept(explicit, next).subscribe();

    expect(seen!.headers.get(TENANT_HEADER)).toBe('globex');
  });

  // ---- platform API ----------------------------------------------------
  //
  // The console and the hotel app share a browser, so both sessions can be open
  // at once. Everything below is about which token reaches which API and which
  // one is held back.

  it('sends the platform token to a platform call', () => {
    const req = runWithBothTokens(`${PLATFORM_BASE}/tenants`, null, null, 'platform-tok');
    expect(req.headers.get('Authorization')).toBe('Bearer platform-tok');
  });

  it('never sends the hotel token to a platform call', () => {
    // The backend signs platform tokens with a different key, so this would be
    // a 401 at best. Asserted because the failure mode of getting it wrong is
    // "the console appears to work for hotel users".
    const req = runWithBothTokens(`${PLATFORM_BASE}/tenants`, 'acme', 'hotel-tok', null);
    expect(req.headers.has('Authorization')).toBe(false);
  });

  it('sends no hotel header to a platform call', () => {
    // A platform caller belongs to no hotel; naming one would make the backend
    // read the request as a hotel request.
    const req = runWithBothTokens(`${PLATFORM_BASE}/tenants`, 'acme', null, 'platform-tok');
    expect(req.headers.has(TENANT_HEADER)).toBe(false);
  });

  it('sends the hotel token to a hotel call even while a platform session is open', () => {
    const req = runWithBothTokens(
      `${BASE_URL}/api/v1/user/list`, 'acme', 'hotel-tok', 'platform-tok',
    );
    expect(req.headers.get('Authorization')).toBe('Bearer hotel-tok');
    expect(req.headers.get(TENANT_HEADER)).toBe('acme');
  });

  it('leaves the platform sign-in unauthenticated', () => {
    // Login is public on both sides. A token left over from an earlier session
    // must not ride along, and the temp-token step must not be given one.
    const req = runWithBothTokens(`${PLATFORM_BASE}/auth/login`, null, null, 'platform-tok');
    expect(req.headers.has('Authorization')).toBe(false);
  });

  it('treats the whole platform namespace as one audience', () => {
    // Every endpoint under the prefix, not a list of them: a new endpoint added
    // later inherits the rule rather than needing to be remembered here.
    for (const path of ['/auth/me', '/admins', '/audit-logs', '/lookups/timezones']) {
      const req = runWithBothTokens(
        `${PLATFORM_BASE}${path}`, 'acme', 'hotel-tok', 'platform-tok',
      );
      expect(req.headers.get('Authorization')).withContext(path).toBe('Bearer platform-tok');
      expect(req.headers.has(TENANT_HEADER)).withContext(path).toBe(false);
    }
  });

  it('does not mistake a hotel path that merely mentions the platform', () => {
    const req = runWithBothTokens(
      `${BASE_URL}/api/v1/platform-notes`, 'acme', 'hotel-tok', 'platform-tok',
    );
    expect(req.headers.get('Authorization')).toBe('Bearer hotel-tok');
    expect(req.headers.get(TENANT_HEADER)).toBe('acme');
  });
});
