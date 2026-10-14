import { scopedStorageKeys } from './storage-keys';

/**
 * A session belongs to the hotel that created it, so the tenant is part of the
 * key. `STORAGE_KEYS` is this function applied to the current host; here the
 * rule itself is pinned, including the no-tenant fallback.
 */
describe('scopedStorageKeys', () => {

  it('suffixes both keys with the tenant slug', () => {
    const keys = scopedStorageKeys('acme');
    expect(keys.ACCESS_TOKEN).toBe('app_accessToken_acme');
    expect(keys.USER_DATA).toBe('app_userData_acme');
  });

  it('leaves the base name alone when the host names no tenant', () => {
    const keys = scopedStorageKeys(null);
    expect(keys.ACCESS_TOKEN).toBe('app_accessToken');
    expect(keys.USER_DATA).toBe('app_userData');
  });

  it('does not collide two tenants', () => {
    expect(scopedStorageKeys('acme').ACCESS_TOKEN)
      .not.toBe(scopedStorageKeys('globex').ACCESS_TOKEN);
  });
});
