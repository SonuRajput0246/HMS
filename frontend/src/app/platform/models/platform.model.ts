/**
 * Wire shapes for the platform (super admin) API.
 *
 * These mirror `backend/src/api/services/tenant_management_service.py` and
 * `super_admin_auth_service.py` exactly, including the derived `status` word
 * the backend computes from the two flags -- the UI renders one label rather
 * than re-deriving active/inactive/archived from `is_active` + `is_deleted`.
 */

export type TenantStatus = 'active' | 'inactive' | 'archived';

export interface IPlatformProfile {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  mfa_enabled?: boolean;
  last_password_update_at?: string | null;
}

export interface IPlatformLoginData {
  access_token: string;
  profile: IPlatformProfile;
}

/**
 * The first step's answer when MFA is involved: no session yet, just a
 * short-lived token to present alongside the code. Its presence (rather than
 * `access_token`'s) is what tells the login screen to move to the second step
 * instead of finishing the sign-in.
 *
 * `mfa_setup_required` splits that second step in two. MFA is compulsory for
 * every platform administrator, so an account that has not enrolled yet is
 * handed `qr_uri`/`secret` *with* the token and must confirm a code from the
 * app it just scanned before `verify-mfa` will issue a session. An account that
 * is already enrolled gets no secret -- it only has to prove the one it has.
 */
export interface IPlatformMfaChallenge {
  mfa_required: true;
  mfa_setup_required: boolean;
  temp_token: string;
  qr_uri?: string;
  secret?: string;
}

/** Enrolment payload: the otpauth URI to render as a QR, plus its secret. */
export interface IPlatformMfaSetup {
  qr_uri: string;
  secret: string;
}

export interface ITenantSummary {
  total_tenants: number;
  active_tenants: number;
  inactive_tenants: number;
  archived_tenants: number;
  total_users: number;
}

export interface ITenant {
  id: number;
  name: string;
  slug: string;
  timezone: string;
  currency: string;
  is_active: boolean;
  is_deleted: boolean;
  status: TenantStatus;
  created_at?: string | null;
  updated_at?: string | null;
  deleted_at?: string | null;
  user_count?: number | null;
    /**
   * The tenant's newest administrator invitation, or `null` if it has never
   * had one (pre-dating the invitation flow, or seeded). Returned by
   * `GET /tenants/<id>` so the edit screen can offer a resend only when there
   * is a live record behind it.
   */
  admin_invitation?: ITenantInvitation | null;
}

/** Lifecycle of one invitation link, as the backend's `status_of` derives it. */
export type InvitationStatus = 'pending' | 'accepted' | 'expired' | 'revoked';

/**
 * One `tenant_admin_invitations` row, as serialized by
 * `tenant_invitation_service._serialize` -- both the tenant detail response
 * and the invitation preview endpoint speak this shape.
 */
export interface ITenantInvitation {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  status: InvitationStatus;
  expires_at: string | null;
  accepted_at: string | null;
  invited_by?: string | null;
  created_at: string | null;
}

/**
 * Create payload: the tenant and its first administrator. There is no
 * password here by design -- the administrator sets one by accepting the
 * emailed invitation link, so the only credential this form produces is an
 * address to send it to.
 */
export interface ICreateTenant {
  name: string;
  slug: string;
  timezone: string;
  currency: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_email: string;
  admin_mode?: 'owner' | 'invitation';
  admin_password: string;
}


/** Partial edit payload -- the service only touches fields that are present. */
export interface IUpdateTenant {
  name?: string;
  slug?: string;
  timezone?: string;
  currency?: string;
}

/**
 * The deployment the console is running against, served by
 * `GET /api/v1/platform/config` and derived on the server from the
 * `PUBLIC_BASE_URL` variable in the backend's `.env`.
 *
 * Nothing here is a client-side guess: `localhost` used to be hardcoded in the
 * subdomain column, the slug suffix and the URL preview, so all three printed a
 * development host the moment the panel was served from a real one.
 */
export interface IPlatformConfig {
  /** e.g. `http://localhost:4200`, `https://console.example.com`. */
  public_base_url: string;
  /** e.g. `localhost:4200`, `example.com` -- what a tenant slug is prefixed with. */
  tenant_host_suffix: string;
}

/**
 * One row of the `currencies` table, as offered by the tenant form's picker.
 *
 * `code` is the value written back to the tenant; `name` and `symbol` exist
 * only so the option can say "INR - Indian Rupee" instead of asking the
 * operator to know what a bare three-letter code means.
 */
export interface ICurrencyOption {
  code: string;
  name: string;
  symbol?: string | null;
}

/**
 * One IANA zone, exactly the string `ZoneInfo` validates on save -- served
 * from Python's own zone data, so an option offered here can never be
 * rejected by `tenant_management_service`.
 */
export interface ITimezoneOption {
  name: string;
}

/**
 * One row of `audit_logs`, as served by `GET /api/v1/platform/audit-logs`.
 *
 * `details` is the free-form JSON text the writer stored (changed fields,
 * previous/next values) and is deliberately typed as a raw string: it is shown
 * to the operator verbatim, not parsed into a shape the UI then has to trust.
 * `actor_email` is copied in at write time and may outlive the account, which
 * is why it is shown instead of joined from `super_admin_id`.
 */
export interface IAuditLog {
  id: number;
  super_admin_id: number | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  details: string | null;
  ip_address: string | null;
  created_at: string | null;
}

/**
 * A platform operator, as served by `GET /api/v1/platform/admins`. Never
 * carries the password or the MFA secret -- the server strips both.
 */
export interface ISuperAdmin {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  is_deleted: boolean;
  mfa_enabled: boolean;
  /** Set while the account is in a brute-force lockout; null otherwise. */
  locked_until?: string | null;
  last_password_update_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Create payload for a new operator. The password is set out of band. */
export interface ICreateSuperAdmin {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

/** Partial edit payload -- the service only touches fields that are present. */
export interface IUpdateSuperAdmin {
  first_name?: string;
  last_name?: string;
  email?: string;
}
