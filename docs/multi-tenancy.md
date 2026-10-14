# Multi-Tenancy — Architecture & Design

Status: **design agreed. Phases 1 (tenant registry & resolution), 2 (model scoping), 3 (enforcement),
4 (auth integration) and 5 (provisioning & seeders, brought forward) are implemented and verified in a
scratch database. Per-tenant config and frontend are not started — see §11.**
Owner: this repo. Supersedes the earlier `INSTANCE_TYPE` (HMS/CMS) switch, which is gone.

---

## 1. Decisions (locked)

| Question | Decision |
|---|---|
| Isolation model | **Shared schema + `tenant_id` discriminator**, enforced centrally |
| Tenant resolution | **Subdomain** (`acme.hms.example.com`) |
| Tenant granularity | **One property = one tenant** |
| Platform administration | **In-app platform super-admin** |
| Per-tenant config | **`system_settings` and `templates` are per-tenant**; enums, inventory units, countries/states/cities/currencies and the modules menu tree stay **global** |
| Existing data | **Disposable** — the database is recreated; no backfill |

Stack is Flask blueprints + SQLAlchemy 2.0 ORM + Alembic + **MySQL/MariaDB** (inferred from
`mysql://` URL, `mysql_prefix="FULLTEXT"`, `CHAR_LENGTH(...)` check constraints).
MySQL has no schema namespace distinct from a database, so "schema per tenant" would have
meant database-per-tenant; it was rejected in favour of shared schema.

---

## 2. Current state (what the design has to fit)

- **One engine, one session.** `src/database/session.py` builds a single `create_engine(DATABASE_URL)`
  wrapped in a module-level `scoped_session` (`db_session`). Services receive it as `self.db`.
- **32 mapped classes, zero tenant concept.** A grep for `tenant|organization|company|property|branch`
  finds nothing but an unrelated `company_name` email variable.
- **One auth choke point.** `authenticate()` in `src/api/middlewares/auth_middleware.py` decodes the
  JWT, loads `User`, checks the `tokens` row is not revoked, and sets `g.current_user`. Every
  authenticated route passes through it, either directly (`jwt_required`) or via
  `authorization.requires_module()`.
- **Authorization is already role-keyed.** `granted_module_names(role_id)` joins
  `modules ✕ role_module_access`. Roles become tenant-scoped, so this inherits tenancy for free.
- **Two inheritance roots.** Most models extend `BaseModel` (`is_deleted`, `created_at`, `updated_at`,
  `deleted_at`); `Prefixes`, `Token` and `SystemSetting` extend `Base` directly. A tenancy mixin must
  therefore not depend on `BaseModel`.
- **Timestamps are set by ORM events**, not column defaults (`before_insert` / `before_update` in
  `src/api/events/`). A tenant-stamping listener belongs in that same idiom.
- **Only one raw-SQL fragment in runtime code** — `MATCH(...) AGAINST` in
  `src/api/services/user_service.py:39` — and it sits inside an ORM `select()` filter, so it stays
  inside any ORM-level scoping. Seeders use `sql_statement_loader` but run outside request scope.

---

## 3. The tenancy boundary

### 3.1 Global — shared by every tenant

| Table(s) | Why global |
|---|---|
| `countries`, `states`, `cities`, `currencies` | Universal reference data. ~250 currencies and the world's geography; duplicating per hotel is pure waste with no isolation benefit. |
| `modules` | The menu tree is product-owned; there is one product. Tenant variation lives in `role_module_access`, which *is* tenant-scoped. |
| `enum_definitions`, `enum_options` | Form-field definitions describe universal hotel concepts (per decision). |
| `inventory_units` | Shared starter catalogue (per decision). |

### 3.2 Platform — above all tenants (new)

| Table | Purpose |
|---|---|
| `tenants` | The registry: slug, name, status |
| `platform_users` | Identities that administer tenants. Deliberately **not** rows in `users`. |

### 3.3 Tenant-scoped — gets a `tenant_id`

| Group | Tables |
|---|---|
| Identity & access | `users`, `roles`, `role_module_access`, `tokens`, `email_otps`, `account_deletions` |
| Booking domain | `guests`, `additional_guests`, `reservations`, `reservation_primary_guests`, `reservation_additional_guests`, `payments` |
| Property | `rooms`, `room_types`, `room_amenities`, `room_type_amenities`, `room_blocks` |
| Stock | `inventory`, `inventory_categories` |
| Numbering | `prefixes`, `reservation_sequences` |
| Config & content | `system_settings`, `message_templates`, `login_sliders` |

### 3.4 Foreign-key boundaries

The guard in §5.3 must allow tenant→global edges but forbid tenant→*other*-tenant edges.
The full graph has exactly five legitimate cross-boundary edges:

```
role_module_access.module_id        -> modules.id        (global)
guests.city_id                      -> cities.id        (global)
guests.state_id                     -> states.id        (global)
guests.country_id                   -> countries.id     (global)
guests.nationality_id               -> countries.id     (global)
```

Every other FK joins tenant→tenant (`users.role_id -> roles`, `tokens.user_id -> users`,
`reservations.room_id -> rooms`, `payments.reservation_id -> reservations`,
`reservation_sequences.prefix_id -> prefixes`, `room_type_amenities.amenity_id -> room_amenities`, …).

**This list is not maintained by hand.** The guard derives it by asking whether the *target* class is
tenant-scoped. A hand-written list would silently rot the first time a model is added.

---

## 4. Schema changes

### 4.1 New tables

```
tenants
  id            PK
  slug          VARCHAR(63)  UNIQUE   -- DNS label: [a-z0-9-], no leading/trailing hyphen
  name          VARCHAR(150)          -- display name
  is_active     BOOL                  -- provisioned & usable
  is_suspended  BOOL                  -- administratively blocked
  suspended_reason VARCHAR(255) NULL
  created_at, updated_at, is_deleted, deleted_at

platform_users
  id, email UNIQUE, password, first_name, last_name
  is_active, mfa_enabled, mfa_secret
  last_password_update_at
  created_at, updated_at, is_deleted, deleted_at
```

`platform_users` is separate from `users` on purpose. The alternative — `users.tenant_id` nullable,
NULL meaning "platform" — makes `tenant_id` mean two things and turns one forgotten filter into
a cross-tenant exposure of the highest-privilege accounts in the system. A separate table keeps
`users.tenant_id` **`NOT NULL`**, so the invariant is absolute.

### 4.2 The mixin

```python
class TenantScoped:
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
```

A plain mixin, not a `BaseModel` subclass, because `Token`, `Prefixes` and `SystemSetting` extend
`Base` directly (§2). Applied to every class in §3.3.

### 4.3 Constraints that must become composite

These are global today and would collide across tenants:

| Table | Now | Becomes |
|---|---|---|
| `roles` | `role_code` UNIQUE | `UNIQUE(tenant_id, role_code)` |
| `reservations` | `reservation_number` UNIQUE | `UNIQUE(tenant_id, reservation_number)` |
| `prefixes` | `UNIQUE(purpose)` | `UNIQUE(tenant_id, purpose)` |
| `system_settings` | `key` PRIMARY KEY | `PRIMARY KEY(tenant_id, key)` |
| `reservation_sequences` | `UNIQUE(prefix_id, year, month)` | `UNIQUE(tenant_id, prefix_id, year, month)` |
| index `ix_active_role_code` | `(is_deleted, role_code)` | `(tenant_id, is_deleted, role_code)` |

**`reservations.reservation_number` was missed in the first draft and found while implementing.** It is
`unique=True` today. Numbers are minted from `reservation_sequences`, which are themselves per-tenant,
so two hotels legitimately generate the same `RES-202610-00001` — a global `UNIQUE` would refuse the
second hotel's first booking of the month. This was the highest-value catch of Phase 2, because the
failure only appears once a second tenant exists.

**`message_templates` deliberately gains NO unique constraint.** The model already refuses one, with a
comment explaining why: MySQL has no partial indexes, so `UNIQUE(code, channel)` would also cover
soft-deleted rows and make it impossible to re-create a template with the same code after deleting it.
Uniqueness among live rows stays in the CRUD service. Anything consistent with the existing rule must
also become per-tenant, but that belongs in the service, not the schema.

Indexes in tenant-scoped tables largely still lead with `is_deleted` rather than `tenant_id`. Every
lookup can still use the `ix_<table>_tenant_id` index the mixin adds, so this is a performance
question, not a correctness one. Prefixed composite indexes are left to Phase 3/8, where the scoped
queries exist and their plans can be measured.

**`users.email`** is the deliberate exception, and was confirmed: it stays *non-unique*, with the index
widened to `(tenant_id, is_deleted, email)`. `register_user()` does a manual `email + is_deleted=False`
existence check, which lets a soft-deleted user's email be re-registered; a hard
`UNIQUE(tenant_id, email)` would break that.

### 4.4 Migrations

Single migration set; the schema is created tenant-aware from the start. Per the standing
instruction, **migration files are not touched by this work** — models are changed and the
migrations are regenerated by hand.

---

## 5. Enforcement

### 5.1 Tenant context

A `ContextVar[int | None]` in `src/database/tenant_context.py`, not `flask.g`, because seeding and
provisioning run with no request. Helpers:

```python
current_tenant_id()            -> int | None
tenant_context(tenant_id)      # context manager; used by provisioning & seeders
bypass_tenant_filter()         # context manager; explicit, greppable, for admin/reporting-only
set_tenant_context(tenant_id)  # request path
```

### 5.2 Read and write filtering

Implemented in `src/database/tenant_enforcement.py`. The listeners are attached to the `Session`
class by importing the module, and `src/database/session.py` imports it — so *obtaining a session at
all* is what turns enforcement on, for the app, the seeders, the scripts and any test alike.

One `do_orm_execute` listener scopes reads and ORM bulk writes:

```python
@event.listens_for(Session, "do_orm_execute")
def _scope_to_tenant(state):
    if state.execution_options.get("skip_tenant_filter"):
        return
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return
    if not isinstance(state.statement, (Select, Update, Delete)):
        return                      # an INSERT has no WHERE; a TextClause has no .options()
    state.statement = state.statement.options(
        with_loader_criteria(TenantScoped, lambda cls: cls.tenant_id == tenant_id,
                             include_aliases=True)
    )
```

`Session.get` is wrapped separately, because it answers from the identity map before it emits SQL —
see §5.3.

One `before_flush` listener does three jobs on the rows about to be written:

- **stamp** `tenant_id` on new tenant-scoped rows from the current context, raising
  `TenantContextMissingError` when the context is `None` — an unscoped insert is a programming error,
  not something to default;
- **guard** object-graph relationships assigned in Python — a tenant-scoped relationship whose
  target's `tenant_id` differs is refused with `CrossTenantReferenceError`;
- **guard** scalar foreign keys, batched to one lookup per target class per flush — a foreign key
  whose target row is not in the current tenant is refused.

The set of guarded edges is **derived from the mapper, not hand-written**: an edge is guarded exactly
when its target class inherits `TenantScoped`. That is what allows the five tenant → global edges
(§3.4) without naming them, and what covers a model added later with no edit here.
`bypass_tenant_filter()` suppresses the read filter but does **not** authorise an unscoped write; a
cross-tenant write still names its tenant with `tenant_context(tenant_id)`, because a write with no
tenant is always a bug.

This is **deny-by-default and central**: a new model that inherits `TenantScoped` is filtered
automatically, and a service that forgets a filter is still safe.

The refusals are `RuntimeError` subclasses, deliberately *not* `SQLAlchemyError`, so a service that
wraps `commit()` in `except SQLAlchemyError` cannot swallow them. `CrossTenantReferenceError` maps to
a 400 in `src/api/utils/error_handlers.py`; `TenantContextMissingError` is a server fault and falls
through to the generic 500.

### 5.3 Spike results — proven, not assumed

All four were probed against a throwaway database before the layer was trusted, and are now asserted
by the leak test. SQLAlchemy 2.0.44.

1. **`Session.get()`** — the database lookup *is* filtered, but a hit in the identity map returns
   before any SQL runs, so loader criteria never see it. A row loaded under `bypass_tenant_filter()`
   therefore stayed visible after the tenant switched. **Closed** by wrapping `Session.get()`: an
   identity-map hit that belongs to another tenant returns `None`, which is what the read filter would
   have done had a query run. This is the one real gap the spike found.
2. **Bulk `Query.update()` / `Query.delete()`** — both fire `do_orm_execute` and honour
   `with_loader_criteria`; the emitted SQL is scoped, and `synchronize_session` (default `auto`) does
   not defeat it. So `auth_service.logout_user`, the token revocation in `generate_user_session`,
   `guest_service.handle_additional_guests`, `admin_service`'s role-permission rewrite and
   `role_seeder._assign_role_permissions` are all scoped with no change to them.
3. **`text()` and raw connections** — a raw `TextClause` is skipped by the `isinstance` check, and
   `tenant_leak_audit.py` fails on any raw SQL executed outside the seeder allowlist. It reads clean.
4. **Relationship loading** — `include_aliases=True` filters eager-loaded (`lazy="joined"`) parents
   too; proven against the real eager-loaded `reservations → created_by_user` and
   `reservation_sequences → prefix` rows.

A `src/database/scripts/tenant_leak_audit.py`, mirroring the existing `audit_authorization.py` idiom,
greps for `text(`, `Session.get`, `session.connection(`, Core/bulk update/delete, and every
`skip_tenant_filter` / `bypass_tenant_filter` use — so each one is a reviewed decision. It is
read-only and needs no database.

---

## 6. Tenant resolution & auth

### 6.1 Resolution order

A `before_request` hook resolves the tenant **before** `authenticate()` runs, because `User` is
tenant-scoped and its lookup needs the tenant first.

1. **Subdomain of `Host`** (production; app and API same-origin behind a proxy).
2. **`X-Tenant` header** (development and cross-origin). The frontend derives it from the subdomain.
3. If both are present they must agree.

Then load `Tenant` by slug and stash it on `g`. Unknown slug → 404; `is_suspended` → 403; a request
that names **no** tenant at all → 404 as well. The last one is not pedantry: without it a header-less
request would run with no tenant filter, and the login route's `users` lookup could match a row from
any hotel.

**Skipped for** `/api/v1/platform/*` (platform routes are above tenants), health checks, and static
assets. The skip list is explicit and greppable.

### 6.2 JWT

**Implemented (Phase 4a–4d).**

- Access and refresh tokens carry a **`tenant_id`** claim; the MFA `mfa_pending` temp token too. The
  value is the user's own `tenant_id`, so the token is pinned to the hotel the account belongs to.
- `authenticate()` requires `claim.tenant_id == current_tenant_id()` and rejects a **missing** claim
  as well as a mismatched one, with 401, *before* it loads the user. A token minted for hotel A is
  therefore structurally useless against hotel B, and a token with no claim cannot fall back to
  whichever tenant the request happened to resolve to.
- The refresh path (`get_fresh_tokens`) and the MFA path (`verify_mfa_login`) check the same claim.
  The refresh one matters because a browser sends its cookie to whatever host it is talking to; in
  development two hotels share `localhost`, so the claim is the only thing separating them.
- **Refresh cookie:** `hms_refreshToken` is set with no `Domain` attribute, so it is **host-only**
  already — `acme.hms.example.com` will not send it to `beta.hms.example.com`. The claim check is the
  second line of defence. (`COOKIE_SECURE` / `COOKIE_SAMESITE` are read from the environment.)
- `user_login`, `verify_email`, `activate_account`, `reset_user_password`, `send_otp_on_email` and
  `get_fresh_tokens` are tenant-aware implicitly once the tenant is resolved, because their `User`
  lookups are auto-filtered by the enforcement layer.

Verified by `src/database/scripts/tenant_auth_test.py` (`hms_authtest` scratch database, 13/13):
login mints a bound token; the token is accepted at its own hotel and refused at another; a
claim-less or foreign-claim token is refused; the cookie is refused cross-hotel; a header-less login
is 404; another hotel's credentials are refused; and the temp MFA token is bound too.

### 6.3 Platform authentication

**Implemented (Phase 4e).** The operator who sits above every hotel is a row in `platform_users`, not
in `users`. They authenticate with a **separate secret** (`PLATFORM_JWT_SECRET_KEY`; unset by default,
so platform routes refuse every call rather than degrade into "any token is fine") and a distinct
`scope: "platform"` claim. A hotel token therefore fails signature verification on a platform route and
a platform token fails it on a hotel route — the scope check is the second line of defence.

`src/api/middlewares/platform_auth.py` is the gate, the counterpart of `authenticate()`:
`platform_required` decodes with the platform secret, requires the scope, loads the (non-tenant-scoped)
`PlatformUser`, and stashes it on `g`. Routes under `/api/v1/platform/`, which the tenant resolver is
exempt for:

- `POST /login` — public; mints a platform token.
- `GET /tenants` — list every hotel.
- `POST /tenants` — provision one (calls `provision_tenant`; §7).
- `POST /tenants/<id>/suspend` and `.../reactivate` — the toggle the resolver enforces as 403.
- `POST /tenants/<id>/reset-admin-password` — resets the hotel's `SUPER_ADMIN` password **and revokes
  its live tokens**, so the reset is not cosmetic.

Verified by `src/database/scripts/platform_auth_test.py` (`hms_platformtest`, **20/20**): both
cross-audience directions are refused; provisioning through the route yields a working hotel admin; a
suspended hotel's requests are 403 and reactivation restores them; and a password reset stops the old
password and the tokens it had bought.

Platform tokens are **stateless** — there is no `platform_tokens` table, so a session cannot be revoked
before it expires (default 60 minutes). Platform MFA is not wired either. Both are deliberate; see §10.

---

## 7. Provisioning

Brought forward ahead of Phase 3, because every seeder had to be touched for tenancy anyway and
provisioning is just the ordered call of them.

`provision_tenant(slug, name, admin_email, admin_password, …)`:

1. Create the `tenants` row and commit it. Seeders own their own sessions and commit independently,
   so a tenant that is not durable first would leave seeded rows pointing at an id that never was.
2. Seed the tenant's **roles + `role_module_access`**, from the global `modules` tree.
3. Seed **`prefixes`** and **`reservation_sequences`** (a sequence belongs to a prefix).
4. Seed default **`system_settings`** (`default_currency`) and **`message_templates`** (the 3 OTP
   rows).
5. Seed default **`login_sliders`**.
6. Create the tenant's first **`users`** row, in its own `SUPER_ADMIN` role.

Re-running is safe: every seeder checks for its own rows first, so a half-finished provision is
repaired by running it again rather than by cleaning up.

The old `system_setting_seeder` / `template_seeder` data **stayed where it was** — inside those
seeders — rather than moving to a separate `tenant_defaults` module. That data *is* the default, so a
second copy in another module would just be a second thing to keep in sync. Countries, states,
cities, currencies, enums, units and modules are global and seeded once, never per tenant.

### 7.1 Not one transaction, and why that is fine

The original plan said "in one transaction". It is not one, and pretending otherwise would be worse
than the reality. Today every seeder opens its own `db_session`, commits, and calls
`db_session.remove()`; forcing a single shared transaction would mean rewriting all nineteen of them
at once, which is a far larger and riskier change than this phase needs. The property that actually
matters — *re-running repairs a partial provision* — is delivered by idempotency instead.

### 7.2 The seeder split

Seeders now divide by ownership, and the `tenant_id` parameter is what enforces it:

| Kind | Seeders | `tenant_id` |
|---|---|---|
| **Platform** | countries/states/cities, currencies, enums, inventory units, modules | none — seeded once per install |
| **Tenant defaults** | prefixes, reservation_sequences, system_settings, templates, login_sliders, roles, + the admin user | required |
| **Tenant demo data** | inventory categories/items, room amenities/types/links, rooms, room blocks, guests, additional guests, reservations, reservation links | required |

`seed_platform_data()`, `seed_tenant_defaults()` and `seed_tenant_demo_data()` live in
`run_base_seeders.py`; provisioning calls only the first two. Demo data is **not** seeded for a real
hotel — it starts empty.

Every tenant seeder resolves its tenant via `_seeding.resolve_tenant_id()`: an explicit `tenant_id=`
argument first, else the ambient `tenant_context`, else it **raises**. There is deliberately no
"default tenant", because seeding into the wrong hotel would be silent — the rows would insert
cleanly and belong to someone else.

The existence checks are tenant-filtered too, not just the inserts. Without that, seeding the second
hotel finds the first hotel's `Food` category, room 101, or `RES` prefix, concludes it already
exists, and leaves the new hotel with nothing at all.

One order inside demo data is load-bearing: `reservations.created_by` is a **NOT NULL foreign key**
to `users.id`, and the seeder used to hardcode `created_by: 1`. Under tenancy that is a cross-tenant
reference. It now resolves the tenant's own admin, so the admin user must be seeded before demo data.

### 7.3 The session-detachment hazard (remember this)

`db_session` is a **thread-scoped** session, and each seeder calls `db_session.remove()` when it
finishes — that is `Session.close()`, which **expires every object the session holds**. Three
consequences, all hit while verifying this phase:

* An ORM instance captured *before* a seeder runs is unusable *after* it. Reading any attribute
  raises `DetachedInstanceError`, because the close expired it.
* Because `db_session` is shared per thread, provisioning a second tenant detaches objects returned
  by the first.
* `provision_tenant()` therefore returns an **expunged** `Tenant`: re-read after all seeding, then
  detached with its attributes still loaded, so the caller can read `slug`/`name` no matter what runs
  next.

Any future code that holds an ORM object across a seeding boundary is a bug. Capture ids as plain
ints instead.

---

## 8. Frontend

| Piece | Change |
|---|---|
| `InstanceService` | Becomes tenant-aware: `slug` from `window.location.hostname`'s first label; `label` (from a public tenant-info endpoint), `prefix` and `homeUrl` stay `/hms/...`. |
| HTTP interceptor (`core/http-interceptor.ts`) | Adds `X-Tenant: <slug>` on every request, including pre-login calls. |
| Token storage key | `app_accessToken` becomes `app_accessToken_<slug>`. The current key is already wrong (see §10) and would become a genuine cross-tenant bug once one browser can reach two tenants. |
| Boot | `config.json` keeps `api_base_url` only; tenant identity is **not** a build-time value. |
| Login | Optionally show the tenant's name via a public `GET /api/v1/common/tenant-info`. |
| Unknown subdomain | The frontend routes to the 404 page; the API returns 404. |

### Local development

`.localhost` is specified to resolve to loopback, so `acme.localhost:4200` works with no hosts-file
edit in current browsers. The frontend then sends `X-Tenant: acme` to `localhost:5000`. Two tenants
can be driven side by side for testing.

---

## 9. Verification

- **Leak tests (new, Phase 3).** `src/database/scripts/tenant_leak_test.py`. There is no backend test
  suite and no `pytest` in the venv, so it is a self-contained, exit-code script in the same idiom as
  `audit_authorization.py`. It builds a throwaway `hms_leaktest` database with `create_all`, seeds the
  platform, provisions `acme` and `globex`, and gives tenant A a row in **every** scoped table. It was
  written first and run against the Phase-2 tree, where it failed (76 passed / 62 failed: B saw A's
  rows everywhere) — then the enforcement layer was added and it passes **141/141**. It checks:
  coverage of the boundary; that every scoped model emits a `tenant_id` predicate (captured from the
  SQL, so a model added later is covered automatically); that B reads none of A's rows, per table; the
  four §5.3 hazards; and that writes are stamped, an unscoped insert is refused, and a cross-tenant
  foreign key is refused while the same key inside the tenant is allowed. The database is dropped
  afterwards; the dev database is never touched.
- **Seeding (done with Phase 5).** Against a throwaway `hms_seedtest` database built with
  `Base.metadata.create_all`: seed the platform, provision `acme` and `globex`, then assert that each
  holds its own 6 roles, 3 prefixes, 3 sequences, 3 templates, 9 sliders, 1 setting and 1 admin; that
  re-provisioning changes no count; that demo data lands in exactly one tenant; that every
  `tenant_id` is non-null and points at a known tenant; and that both hotels can hold the **same**
  reservation number (`RES-<yyyymm>-00001`), which a global `UNIQUE` would have rejected. Also runs
  `run_base_seeders()` twice to prove the documented dev command is idempotent. The scratch database
  is dropped afterwards; the dev database is never touched.
- **Request-level tests.** `tenant_auth_test.py` (§6.2), `platform_auth_test.py` (§6.3) and
  `tenant_booking_test.py` (§10): a token minted for A is rejected on B; a suspended tenant is 403;
  the hotel and platform identities never cross; and the second hotel can create a reservation and
  record a payment, attributed to its own user.
- **Static audit.** `tenant_leak_audit.py` (§5.3).
- **Regression.** `npm run build` and `npm test` (91 specs) stay at their current baseline; the
  backend boots with `create_app()` as it does now (`APP OK - 65 api routes`).

---

## 10. Explicitly out of scope

- **Pre-existing bugs, not folded in unless asked:** the missing `category` / `inventory_2` menu
  icons (`sidenav.component.html` builds `/assets/menu_icons/<icon>`), and
  `topnav.component.ts:28` reading `localStorage.getItem('token')` when the real key is
  `STORAGE_KEYS.ACCESS_TOKEN` (`'app_accessToken'`). *The second one becomes a tenancy bug in
  Phase 7, so it will likely have to be fixed there anyway.*
- **One hardcoded tenant-scoped id remains.** Three were correct in a single-tenant world and became
  cross-tenant references the moment a second hotel existed. Two are now the authenticated actor, and
  are proven *at the second hotel* by `tenant_booking_test.py`:
  - `reservation_service.create_reservation` — was `created_by=data.get("created_by") or 1`; now
    `get_current_user_id()`. The Angular create payload never sent `created_by`, so the fallback (user
    1) was what always ran. **Fixed.**
  - `payment_service.insert_payment_details` — was `verified_by=1`; now `get_current_user_id()`.
    **Fixed.**
  - `auth_service.py:40` — `role_id=1` for a self-registered user, **still open**, already flagged
    in-code as `## LATER CHANGE IT & SET CUSTOMER/GUEST ROLE_ID`. There is no `GUEST` role in the
    seeder yet, so this needs a product decision (which role self-registration grants), not just a
    lookup. **Note it also means today's public registration hands out the first-seeded role —
    `SUPER_ADMIN` — which is a live authorization bug independent of tenancy.** *(Phase 6.)*
- **Platform auth is deliberately minimal (Phase 4e).** No `platform_tokens` table, so a platform
  session is stateless and cannot be revoked before its expiry (default 60 minutes); no second factor
  on platform login; and no platform-user seeder — the first operator is created out-of-band (a row in
  `platform_users`). Each of these is a product decision rather than a tenancy requirement.
- **Pre-existing, not tenancy-specific:** `authenticate()` skips the revocation check for any token
  carrying a `scope` claim (`auth_middleware.py:78`), which is what lets the `mfa_pending` temp token be
  accepted as a bearer token for its five-minute life — i.e. it bypasses the second factor. It is bound
  to a hotel like any other token now, but it is still a second-factor hole. Not fixed here.
- `material-module.ts` trimming (previously found unsafe to act on).
- `user.service.ts`'s 8 legacy methods against endpoints that no longer exist.
- Group-of-properties modelling — deferred until a chain actually appears.

---

## 11. Phases

| # | Phase | Status | Deliverable | Verified by |
|---|---|---|---|---|
| 1 | Tenant registry & resolution | **done** | `tenants`, `platform_users` models; `tenant_context`; `before_request` resolution; public tenant-info endpoint | App boots unchanged; `acme` resolves to a tenant; platform routes are skipped |
| 2 | Model scoping | **done** | `TenantScoped` mixin on every §3.3 model; composite constraints | Models import clean; migrations regenerated by hand |
| 3 | Enforcement | **done** | `do_orm_execute` filter, `before_flush` stamp + FK guard, `Session.get` wrapper, leak audit script, leak tests | `tenant_leak_test.py` **141/141**; `tenant_leak_audit.py` clean; the four §5.3 hazards proven |
| 4 | Auth integration | **done** | `tenant_id` JWT claim on all token types; `authenticate()` cross-check; host-only refresh cookie; platform auth (`platform_users`, separate secret + scope, `/api/v1/platform/*`); §10 booking/payment ids fixed | `tenant_auth_test.py` **13/13**; `platform_auth_test.py` **20/20**; `tenant_booking_test.py` **9/9**; suspended tenant 403 |
| 5 | Provisioning | **done** (early — see §7) | Tenant-aware seeders; `provision_tenant()`; `seed_platform_data` / `seed_tenant_defaults` / `seed_tenant_demo_data` | Two tenants provisioned into a scratch DB, each isolated (see §9) |
| 6 | Per-tenant config & content | | Per-tenant `system_settings`, templates, branding, email `company_name`, upload paths | Two tenants send differently-branded mail |
| 7 | Frontend | | Tenant-aware `InstanceService`, `X-Tenant` header, per-tenant token key | Two tenants driven side by side in one browser |
| 8 | Verification & docs | | Full pass, leakage + request tests, this doc updated | All of §9 green |

Phase 3 is the one that decides whether this is safe. The leak test was written **first and made to
fail** — against the Phase-2 tree it reported **76 passed / 62 failed**, with B seeing A's rows in
every scoped table — and only then was the filter added to make it pass.

> **The Phase-2 → Phase-3 broken window is closed.** While `tenant_id` was `NOT NULL` with nothing
> stamping it, *writes* to tenant-scoped tables through the API failed with a NOT NULL violation. The
> `before_flush` stamp now fills `tenant_id` from the request context, so the app can be run against a
> migrated database. (The seeders were never affected: Phase 5's seeders set `tenant_id` explicitly,
> which is what let them be verified against a real database early.)

> **Phase 4 → Phase 7 window: the API now requires a tenant on every request.** From Phase 4 a request
> that names no hotel is refused (404) and an authenticated request is refused without a `tenant_id`
> claim (401). The Angular app does not send `X-Tenant` yet — that is Phase 7 — so until then it must
> be driven with the header set, or from a `<tenant>.localhost` host. Backend verifications are
> unaffected (they set the header explicitly), which is why this is a documented window rather than a
> blocker. The alternative is to bring the `X-Tenant` interceptor forward from Phase 7.

---

## 12. Defaults I chose that you may want to correct

1. `users.email` stays non-unique with a `(tenant_id, is_deleted, email)` index, preserving today's
   soft-delete-then-re-register behaviour, rather than `UNIQUE(tenant_id, email)`. **Confirmed and
   implemented in Phase 2.**
2. Branding (logo, display name) lives in per-tenant `system_settings`, not as columns on `tenants`.
3. A tenant's first user gets the tenant's `SUPER_ADMIN` role; the platform admin is a separate
   identity entirely.
4. `enum_definitions` / `enum_options` and `inventory_units` stay global (per the decision), so a
   tenant cannot yet add its own options or units. Easy to move later, awkward to un-share.
