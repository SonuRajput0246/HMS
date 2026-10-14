import {
  HttpEvent,
  HttpHandler,
  HttpHeaders,
  HttpRequest,
} from '@angular/common/http';
import { Observable, of } from 'rxjs';

import { AppConfig } from './config/config';
import { InstanceService } from './config/instance.service';
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

  afterEach(() => {
    sessionStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
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
});
