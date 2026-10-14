import { tenantSlugFromHostname } from './tenant';

/**
 * The tenant is the one thing the frontend must agree on with the backend, so
 * this table is the contract. `src/api/middlewares/tenant_resolver.py`'s
 * `_host_slug` is the authority; these cases are its hostname half.
 */
describe('tenantSlugFromHostname', () => {

  const cases: Array<[string, string | null, string]> = [
    ['acme.localhost', 'acme', 'the documented local-development hotel host'],
    ['acme.localhost:4200', 'acme', 'a port is not part of the hostname'],
    ['globex.hms.example.com', 'globex', 'first label before the base domain'],
    ['a.b.c.d', 'a', 'only the leading label names the tenant'],
    ['ACME.LocalHost', 'acme', 'hostnames are case-insensitive'],
    ['  acme.localhost  ', 'acme', 'surrounding whitespace is ignored'],

    ['localhost', null, 'the bare product host names no hotel'],
    ['localhost:4200', null, 'nor with a port'],
    ['127.0.0.1', null, 'an IP names no hotel'],
    ['127.0.0.1:5000', null, 'nor with a port'],
    ['[::1]', null, 'nor does an IPv6 loopback literal'],
    ['[::1]:4200', null, 'nor with a port'],
    ['example.com', 'example', 'an apex is shaped like a hotel host; it 404s as an unknown one'],

    ['', null, 'an empty hostname is not a hotel'],
  ];

  for (const [hostname, expected, why] of cases) {
    it(`maps "${hostname}" to ${JSON.stringify(expected)} -- ${why}`, () => {
      expect(tenantSlugFromHostname(hostname)).toBe(expected);
    });
  }

  it('does not read the port as part of the slug', () => {
    expect(tenantSlugFromHostname('acme.localhost:9999')).toBe('acme');
  });
});
