/**
 * Browser storage keys shared by both instance types.
 *
 * These used to be named `hms_accessToken` / `hms_userData`, which was wrong
 * the moment a CMS instance existed: the same keys would carry an HMS-named
 * session on a cafe deployment. They are also read from more than one place
 * (the auth guard, the refresh interceptor, and both post-login flows), so a
 * typo in one of them silently drops the session rather than failing loudly.
 */
export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'app_accessToken',
  USER_DATA: 'app_userData',
} as const;