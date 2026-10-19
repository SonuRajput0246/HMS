import { PlatformConfigService } from './platform-config.service';

/**
 * The console's fallback when `GET /api/v1/platform/config` cannot be reached.
 *
 * The console is served from a label of its own -- `admin.localhost`,
 * `console.example.com` -- and a hotel's URL is that host with the label swapped
 * for the hotel's slug. So the fallback drops the console's own label (decided
 * by the same `PLATFORM_HOST_LABELS` the routing split uses) and keeps the rest.
 *
 * In production the server answers instead, from the configured
 * `TENANT_BASE_DOMAIN`, and it has the final say. These cases pin only the
 * fallback.
 */
describe('PlatformConfigService.deriveSuffix', () => {
  it('drops the console\'s own label in development', () => {
    expect(PlatformConfigService.deriveSuffix('admin.localhost', '4200')).toBe('localhost:4200');
    expect(PlatformConfigService.deriveSuffix('console.localhost', '4200')).toBe('localhost:4200');
    expect(PlatformConfigService.deriveSuffix('platform.localhost', '4200')).toBe('localhost:4200');
    expect(PlatformConfigService.deriveSuffix('superadmin.localhost', '4200')).toBe('localhost:4200');
  });

  it('drops the console\'s own label in production', () => {
    expect(PlatformConfigService.deriveSuffix('admin.example.com', '')).toBe('example.com');
    expect(PlatformConfigService.deriveSuffix('console.example.com', '')).toBe('example.com');
  });

  it('keeps a host that is not the console', () => {
    // The dev apex, the production apex, and a hotel's own host: none of these
    // carries the console's label, so nothing may be dropped. A label-count rule
    // ("three or more") gets the second one wrong.
    expect(PlatformConfigService.deriveSuffix('localhost', '4200')).toBe('localhost:4200');
    expect(PlatformConfigService.deriveSuffix('example.com', '')).toBe('example.com');
    expect(PlatformConfigService.deriveSuffix('acme.localhost', '4200')).toBe('acme.localhost:4200');
    expect(PlatformConfigService.deriveSuffix('demo.example.com', '')).toBe('demo.example.com');
  });

  it('never slices an IP literal', () => {
    expect(PlatformConfigService.deriveSuffix('127.0.0.1', '4200')).toBe('127.0.0.1:4200');
    expect(PlatformConfigService.deriveSuffix('[::1]', '4200')).toBe('[::1]:4200');
  });

  it('carries a non-default port through', () => {
    expect(PlatformConfigService.deriveSuffix('admin.example.com', '8443')).toBe(
      'example.com:8443'
    );
  });

  it('lowercases and tolerates a missing host', () => {
    expect(PlatformConfigService.deriveSuffix('ADMIN.EXAMPLE.COM', '')).toBe('example.com');
    expect(PlatformConfigService.deriveSuffix('', '')).toBe('');
  });

  it('tolerates a port already present on the host', () => {
    // window.location.hostname never carries one, but the function is also
    // called with hand-written values, so a stray `:port` must not become a
    // label of its own.
    expect(PlatformConfigService.deriveSuffix('admin.localhost:4200', '4200'))
      .toBe('localhost:4200');
  });
});
