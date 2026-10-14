import { initApp } from './app.module';
import { InitialService } from './services/initial.service';
import { TenantService } from './services/tenant.service';

/**
 * The boot order is the whole point of this test.
 *
 * `tenant-info` needs the `BASE_URL` that `config.json` provides, but Angular
 * runs every APP_INITIALIZER function before awaiting any of them -- so two
 * separate initializers raced, and the tenant call read `BASE_URL` before it
 * had been set. Chaining them inside one initializer is what fixes it, and
 * this pins that the chain really is ordered.
 */
describe('initApp', () => {

  it('loads the config before asking the API about the tenant', async () => {
    const calls: string[] = [];

    const initial = {
      loadAppConfig: async () => { calls.push('config'); },
    } as unknown as InitialService;

    const tenant = {
      load: async () => { calls.push('tenant'); },
    } as unknown as TenantService;

    await initApp(initial, tenant)();

    expect(calls).toEqual(['config', 'tenant']);
  });

  it('does not ask about the tenant when the config fails', async () => {
    let tenantAsked = false;

    const initial = {
      loadAppConfig: async () => { throw new Error('api_base_url missing in config.json'); },
    } as unknown as InitialService;

    const tenant = {
      load: async () => { tenantAsked = true; },
    } as unknown as TenantService;

    await expectAsync(initApp(initial, tenant)()).toBeRejected();
    expect(tenantAsked).toBe(false);
  });
});
