import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { InitialService } from './initial.service';
import { AppConfig } from '../core/config/config';
import { InstanceService } from '../core/config/instance.service';

/**
 * Covers the two-step boot: static config supplies the base URL, the backend
 * supplies the instance type.
 *
 * The mismatch case is the point of this suite. Before this change the frontend
 * read instance_type from config.json and nothing compared it to the backend,
 * so a disagreement produced no error -- just URLs whose endpoints did not
 * exist. These tests pin the three behaviours that must hold: backend wins,
 * backend unreachable falls back, and an unreachable backend does not block
 * boot.
 */
describe('InitialService', () => {

  const CONFIG = {
    global_setting: {
      api_base_url: 'http://localhost:5000',
      instance_type: 'HMS'
    }
  };

  function setup(configJson: any = CONFIG) {
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

  /**
   * Issue a boot and flush only the static-config request.
   *
   * Returns the in-flight promise WITHOUT awaiting it: the promise cannot
   * settle until the instance-config request is flushed by the caller, so
   * awaiting here would deadlock the test. Three microtask yields are enough
   * for loadAppConfig's `await loadStaticConfig()` continuation to run and
   * issue the next request.
   */
  function startBoot(service: InitialService, httpMock: HttpTestingController, cfg: any) {
    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json').flush(cfg);
    return promise;
  }

  /** Let queued microtasks run so pending HTTP calls are issued. */
  async function settle() {
    for (let i = 0; i < 3; i++) {
      await Promise.resolve();
    }
  }

  it('takes the instance type from the backend when they agree', async () => {
    const { service, httpMock } = setup();

    const promise = startBoot(service, httpMock, CONFIG);
    await settle();
    httpMock.expectOne(r => r.url.endsWith('/api/v1/common/instance-config'))
      .flush({ status: true, message: 'ok', data: { instance_type: 'HMS' } });
    await promise;
    httpMock.verify();

    expect(TestBed.inject(AppConfig).get('INSTANCE_TYPE')).toBe('HMS');
  });

  it('prefers the backend over config.json on a mismatch', async () => {
    // config.json says HMS, backend is CMS. The backend must win: it is what
    // decides which endpoints exist.
    const { service, httpMock } = setup();

    const promise = startBoot(service, httpMock, CONFIG);
    await settle();
    httpMock.expectOne(r => r.url.endsWith('/api/v1/common/instance-config'))
      .flush({ status: true, message: 'ok', data: { instance_type: 'CMS' } });
    await promise;
    httpMock.verify();

    expect(TestBed.inject(AppConfig).get('INSTANCE_TYPE')).toBe('CMS');
    // and the resolved value is what InstanceService reads
    expect(TestBed.inject(InstanceService).type).toBe('CMS');
    expect(TestBed.inject(InstanceService).homeUrl).toBe('/cms/dashboard');
  });

  it('falls back to config.json when the backend is unreachable', async () => {
    const { service, httpMock } = setup();

    const promise = startBoot(service, httpMock, CONFIG);
    await settle();
    httpMock.expectOne(r => r.url.endsWith('/api/v1/common/instance-config'))
      .error(new ProgressEvent('network error'));
    // Must resolve, not reject: a down backend should not stop the app booting.
    await expectAsync(promise).toBeResolved();
    httpMock.verify();

    expect(TestBed.inject(AppConfig).get('INSTANCE_TYPE')).toBe('HMS');
  });

  it('falls back when the backend answers without an instance type', async () => {
    const { service, httpMock } = setup();

    const promise = startBoot(service, httpMock, CONFIG);
    await settle();
    httpMock.expectOne(r => r.url.endsWith('/api/v1/common/instance-config'))
      .flush({ status: true, message: 'ok', data: {} });
    await promise;
    httpMock.verify();

    expect(TestBed.inject(AppConfig).get('INSTANCE_TYPE')).toBe('HMS');
  });

  it('defaults to HMS when config.json omits instance_type', async () => {
    const withoutInstance = {
      global_setting: { api_base_url: 'http://localhost:5000' }
    };
    const { service, httpMock } = setup(withoutInstance);

    const promise = startBoot(service, httpMock, withoutInstance);
    await settle();
    httpMock.expectOne(r => r.url.endsWith('/api/v1/common/instance-config'))
      .error(new ProgressEvent('network error'));
    await promise;
    httpMock.verify();

    expect(TestBed.inject(AppConfig).get('INSTANCE_TYPE')).toBe('HMS');
  });

  it('rejects when api_base_url is missing', async () => {
    const broken = { global_setting: { instance_type: 'CMS' } };
    const { service, httpMock } = setup(broken);

    const promise = service.loadAppConfig();
    httpMock.expectOne(r => r.url === 'assets/config.json').flush(broken);

    // Without a base URL there is nothing to call, not even the instance
    // endpoint, so boot genuinely cannot continue.
    await expectAsync(promise).toBeRejected();
    httpMock.verify();
  });

});