import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { InitialService } from './initial.service';
import { AppConfig } from '../core/config/config';

/**
 * Covers the boot sequence: config.json is the only source of runtime config,
 * and a missing api_base_url has to fail the boot rather than render a login
 * page that silently never submits.
 */
describe('InitialService', () => {

  const CONFIG = {
    global_setting: {
      api_base_url: 'http://localhost:5000',
      terms_condition_url: '',
      privacy_policy_url: '',
      page_load_time: 1000
    }
  };

  function setup() {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });

    const service = TestBed.inject(InitialService);
    const httpMock = TestBed.inject(HttpTestingController);
    return { service, httpMock };
  }

  it('reads the base URL out of config.json', async () => {
    const { service, httpMock } = setup();

    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json').flush(CONFIG);
    await promise;
    httpMock.verify();

    expect(service.baseUrl).toBe('http://localhost:5000');
    expect(TestBed.inject(AppConfig).get('BASE_URL')).toBe('http://localhost:5000');
  });

  it('resolves even when the static file omits the optional keys', async () => {
    const minimal = { global_setting: { api_base_url: 'http://localhost:5000' } };
    const { service, httpMock } = setup();

    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json').flush(minimal);
    await expectAsync(promise).toBeResolved();
    httpMock.verify();

    expect(service.baseUrl).toBe('http://localhost:5000');
  });

  it('rejects when api_base_url is missing', async () => {
    const broken = { global_setting: { terms_condition_url: '' } };
    const { service, httpMock } = setup();

    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json').flush(broken);

    // Without a base URL there is nothing to call, so boot genuinely cannot
    // continue.
    await expectAsync(promise).toBeRejected();
    httpMock.verify();
  });

  it('rejects when config.json itself cannot be fetched', async () => {
    const { service, httpMock } = setup();

    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json')
      .error(new ProgressEvent('network error'));

    await expectAsync(promise).toBeRejected();
    httpMock.verify();
  });

});