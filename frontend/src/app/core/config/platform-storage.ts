/**
 * Browser storage keys for the platform console session.
 *
 * These deliberately do NOT reuse `STORAGE_KEYS` (which is tenant-scoped) even
 * though both are read by the same interceptor. The two sessions can be open in
 * one browser at the same time -- an operator signed in to the console while a
 * hotel is also open in another tab -- and a shared key would send one
 * population's token to the other's API, where it is rejected at best and, if a
 * guard ever only checked for a token's presence, accepted at worst.
 *
 * The names are therefore fixed rather than slug-scoped: the console belongs to
 * no hotel, so there is nothing to scope them by. `PROFILE_KEY` survives a
 * reload (it is display data, not a credential); the token does not, because
 * `sessionStorage` is the only thing standing between a closed tab and a live
 * console session.
 */

export const PLATFORM_ACCESS_TOKEN_KEY = 'platform_accessToken';
export const PLATFORM_PROFILE_KEY = 'platform_profile';
