import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { TenantService } from './tenant.service';
import { AppConfig } from '../core/config/config';
import { InstanceService } from '../core/config/instance.service';

/**
 * Boot must never reject, and must tell "this hotel does not exist" apart from
 * "the API could not be reached". Both are covered here, along with the
 * branding the login page reads.
 */
describe('TenantService', () => {

  const TENANT_INFO_URL = 'http://localhost:5000/api/v1/common/tenant-info';

  function setup(slug: string | null) {
    const instance = { slug, hasTenant: slug !== null, label: 'HMS' };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: InstanceService, useValue: instance },
      ],
    });
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');

    return {
      service: TestBed.inject(TenantService),
      httpMock: TestBed.inject(HttpTestingController),
      instance,
      config: TestBed.inject(AppConfig),
    };
  }

  it('refuses a host that names no hotel, without calling the API', async () => {
    const { service, httpMock } = setup(null);

    await service.load();

    expect(service.state).toBe('no-tenant');
    httpMock.expectNone(TENANT_INFO_URL);
  });

  it('publishes the hotel name and branding once resolved', async () => {
    const { service, httpMock, instance, config } = setup('acme');

    const loading = service.load();
    httpMock.expectOne(TENANT_INFO_URL).flush({
      status: true,
      message: 'Tenant resolved.',
      data: {
        slug: 'acme',
        name: 'Acme Hotels',
        branding: {
          display_name: 'The Acme Hotel',
          app_logo_image: 'https://cdn/acme.png',
          terms_condition_url: 'https://acme/terms',
          privacy_policy_url: 'https://acme/privacy',
        },
      },
    });
    await loading;

    expect(service.state).toBe('ok');
    expect(instance.label).toBe('The Acme Hotel');
    expect(config.get('COMPANY_NAME')).toBe('The Acme Hotel');
    expect(config.get('TERMS_CONDITION_URL')).toBe('https://acme/terms');
  });

  it('treats a 404 as an unknown hotel', async () => {
    const { service, httpMock } = setup('ghost');

    const loading = service.load();
    httpMock.expectOne(TENANT_INFO_URL)
      .flush({ status: false, message: 'Unknown tenant' }, { status: 404, statusText: 'Not Found' });
    await loading;

    expect(service.state).toBe('unknown');
  });

  it('treats an unreachable API as usable, not as an unknown hotel', async () => {
    const { service, httpMock, instance } = setup('acme');

    const loading = service.load();
    httpMock.expectOne(TENANT_INFO_URL).error(new ProgressEvent('error'));
    await loading;

    /// The product name stands in; the login attempt will surface the outage.
    expect(service.state).toBe('ok');
    expect(instance.label).toBe('HMS');
  });
});
