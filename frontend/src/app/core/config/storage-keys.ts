/**
 * Browser storage keys.
 *
 * These used to be named `hms_accessToken` / `hms_userData`, which baked the
 * product into a key that has nothing to do with the session inside it. They
 * are also read from more than one place (the auth guard, the refresh
 * interceptor, and the post-login flow), so a typo in one of them silently
 * drops the session rather than failing loudly.
 */
export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'app_accessToken',
  USER_DATA: 'app_userData',
} as const;