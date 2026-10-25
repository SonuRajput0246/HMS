import { PlatformConfigService } from './platform-config.service';

/**
 * The console's fallback when `GET /api/super-admin/config` cannot be reached.
 *
 * These cases are the inverse of `backend/src/api/tenancy/resolution.py`, which
 * reads a `Host` header and takes label zero as the tenant slug. They are
 * pinned here because the two must agree: if they ever drift the panel prints a
 * host no tenant answers on -- the same class of bug the hardcoded
 * `localhost:4200` was, only harder to spot.
 */
describe('PlatformConfigService.deriveSuffix', () => {
  it('drops the console\'s own label in development', () => {
    expect(PlatformConfigService.deriveSuffix('admin.localhost', '4200')).toBe('localhost:4200');
  });

  it('keeps the whole host when the console is the dev apex', () => {
    expect(PlatformConfigService.deriveSuffix('localhost', '4200')).toBe('localhost:4200');
  });

  it('drops the console\'s own label in production', () => {
    expect(PlatformConfigService.deriveSuffix('console.example.com', '')).toBe('example.com');
  });

  it('keeps a bare production domain intact', () => {
    expect(PlatformConfigService.deriveSuffix('example.com', '')).toBe('example.com');
  });

  it('carries a non-default port through', () => {
    expect(PlatformConfigService.deriveSuffix('console.example.com', '8443')).toBe(
      'example.com:8443'
    );
  });

  it('never slices an IP literal', () => {
    expect(PlatformConfigService.deriveSuffix('127.0.0.1', '4200')).toBe('127.0.0.1:4200');
    expect(PlatformConfigService.deriveSuffix('[::1]', '4200')).toBe('[::1]:4200');
  });

  it('lowercases and tolerates a missing host', () => {
    expect(PlatformConfigService.deriveSuffix('ADMIN.EXAMPLE.COM', '')).toBe('example.com');
    expect(PlatformConfigService.deriveSuffix('', '')).toBe('');
  });
});
