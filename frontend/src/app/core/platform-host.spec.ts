import { isPlatformHost, PLATFORM_HOST_LABELS } from './platform-host';

/**
 * The host split is what keeps two surfaces in one bundle from reaching each
 * other, so it is pinned rather than trusted: a regression here is silent (the
 * wrong app renders, no error) and would put the hotel app on the console host
 * and vice versa.
 */
describe('isPlatformHost', () => {

  it('recognises every label it declares', () => {
    for (const label of PLATFORM_HOST_LABELS) {
      expect(isPlatformHost(`${label}.localhost`)).toBe(true);
      expect(isPlatformHost(`${label}.example.com`)).toBe(true);
    }
  });

  it('ignores the label in any position but the first', () => {
    // `example.admin.com` is a host under a domain called "admin", not the
    // console. Only the leading label counts.
    expect(isPlatformHost('example.admin.com')).toBe(false);
  });

  it('is case-insensitive and tolerates whitespace', () => {
    expect(isPlatformHost('ADMIN.localhost')).toBe(true);
    expect(isPlatformHost('  Admin.LocalHost  ')).toBe(true);
  });

  it('never treats an IP literal as the console', () => {
    // An IPv4 address's first "label" is not a DNS label, and IPv6 has no dots
    // to speak of. Neither can be a reserved subdomain.
    expect(isPlatformHost('127.0.0.1')).toBe(false);
    expect(isPlatformHost('[::1]')).toBe(false);
    expect(isPlatformHost('::1')).toBe(false);
  });

  it('treats a hotel host as not the console', () => {
    expect(isPlatformHost('demo.localhost')).toBe(false);
    expect(isPlatformHost('grandcentral.example.com')).toBe(false);
  });

  it('treats the apex and localhost as not the console', () => {
    // `localhost` is the product's own dev host, not a reserved subdomain. The
    // hotel app 404s there rather than serving the console, which matches the
    // backend resolving no tenant.
    expect(isPlatformHost('localhost')).toBe(false);
    expect(isPlatformHost('example.com')).toBe(false);
  });

  it('refuses an empty host rather than defaulting to matching', () => {
    expect(isPlatformHost('')).toBe(false);
    expect(isPlatformHost('   ')).toBe(false);
  });

  it('reads the current window when no host is passed', () => {
    // jsdom serves the app from localhost, so this is the hotel case. Pinned so
    // the argument-less default cannot quietly become "always true".
    expect(isPlatformHost()).toBe(isPlatformHost(window.location.hostname));
  });

});
