# Multi-Tenancy — Architecture & Design

Status: **design agreed. Phase 1 (tenant registry & resolution) and Phase 2 (model scoping) are
implemented. No enforcement, auth, provisioning or frontend work yet — see §11.**
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

One `do_orm_execute` listener on `Session`:

```python
@event.listens_for(Session, "do_orm_execute")
def _scope_to_tenant(state):
    if state.execution_options.get("skip_tenant_filter"):
        return
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return
    state.statement = state.statement.options(
        with_loader_criteria(TenantScoped, lambda cls: cls.tenant_id == tenant_id,
                             include_aliases=True)
    )
```

One `before_flush` listener does two jobs: **stamp** `tenant_id` on new tenant-scoped rows from the
current context (raising if the context is `None` — an unscoped insert is a programming error, not
something to default), and **guard** every new/dirty row's tenant-scoped relationships against
cross-tenant assignment (§3.4, derived from the mapper).

This is **deny-by-default and central**: a new model that inherits `TenantScoped` is filtered
automatically, and a service that forgets a filter is still safe.

### 5.3 Gaps to close with a spike (Phase 3, before trusting it)

These are *not* asserted as working; they are the things the spike must prove or work around:

1. **`Session.get()`** — a direct primary-key load may bypass loader criteria. If it does, it needs
   a wrapper or an enforced ban.
2. **Bulk `Query.update()` / `delete()`** — `auth_service.logout_user`, the token-revocation in
   `generate_user_session`, and `role_seeder._assign_role_permissions` all use them today. Whether
   `with_loader_criteria` reaches ORM-enabled bulk statements must be verified, not assumed.
3. **`text()` and raw connections** — currently only one fragment on the request path and it is
   safely inside a `select()`. A static audit script keeps it that way.
4. **Relationship loading** (`lazy="joined"` on `reservation_sequences.prefix` and others) must not
   pull an unfiltered parent row.

A `src/database/scripts/tenant_leak_audit.py`, mirroring the existing
`audit_authorization.py` idiom, greps for `text(`, `Session.get`, `session.connection(`, bulk
update/delete, and every `skip_tenant_filter` use — so each one is a reviewed decision.

---

## 6. Tenant resolution & auth

### 6.1 Resolution order

A `before_request` hook resolves the tenant **before** `authenticate()` runs, because `User` is
tenant-scoped and its lookup needs the tenant first.

1. **Subdomain of `Host`** (production; app and API same-origin behind a proxy).
2. **`X-Tenant` header** (development and cross-origin). The frontend derives it from the subdomain.
3. If both are present they must agree.

Then load `Tenant` by slug and stash it on `g`. Unknown slug → 404; `is_suspended` → 403.

**Skipped for** `/api/v1/platform/*` (platform routes are above tenants), health checks, and static
assets. The skip list is explicit and greppable.

### 6.2 JWT

- Access and refresh tokens gain a **`tenant_id`** claim; the MFA `mfa_pending` temp token too.
- `authenticate()` requires `claim.tenant_id == g.tenant.id` and rejects mismatches with 401. A token
  minted for hotel A is therefore structurally useless against hotel B.
- **Refresh cookie:** currently `hms_refreshToken`, and `COOKIE_SECURE` / `COOKIE_SAMESITE` are
  configured but the `Domain` attribute is the risk. Cookies must be **host-only** (no `Domain`),
  so `acme.hms.example.com` cannot send its cookie to `beta.hms.example.com`. The JWT claim check is
  the second line of defence.
- `AuthService.generate_user_session` and the MFA temp token set the claim; `user_login`,
  `verify_email`, `activate_account`, `reset_user_password`, `send_otp_on_email` and
  `get_fresh_tokens` all become tenant-aware implicitly once the tenant is resolved, because their
  `User` lookups are auto-filtered.

### 6.3 Platform authentication

A **separate secret** (`PLATFORM_JWT_SECRET_KEY`) and a distinct audience/scope claim, so a tenant
token can never be accepted on a platform route or vice versa. Separate routes under
`/api/v1/platform/`: login, list/create tenants, suspend/reactivate, reset a tenant's admin password.

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

- **Leak tests (new).** There is no backend test suite today. Phase 3 introduces one whose first
  test *fails* before the filter exists: provision tenants A and B, insert one row per tenant-scoped
  model in A, assert B reads zero. Run per model, so a newly added model is covered automatically.
- **Seeding (done with Phase 5).** Against a throwaway `hms_seedtest` database built with
  `Base.metadata.create_all`: seed the platform, provision `acme` and `globex`, then assert that each
  holds its own 6 roles, 3 prefixes, 3 sequences, 3 templates, 9 sliders, 1 setting and 1 admin; that
  re-provisioning changes no count; that demo data lands in exactly one tenant; that every
  `tenant_id` is non-null and points at a known tenant; and that both hotels can hold the **same**
  reservation number (`RES-<yyyymm>-00001`), which a global `UNIQUE` would have rejected. Also runs
  `run_base_seeders()` twice to prove the documented dev command is idempotent. The scratch database
  is dropped afterwards; the dev database is never touched.
- **Request-level tests.** A token minted for A is rejected on B (§6.2); a suspended tenant is 403.
- **Static audit.** `tenant_leak_audit.py` (§5.3).
- **Regression.** `npm run build` and `npm test` (91 specs) stay at their current baseline; the
  backend boots with `create_app()` as it does now (`APP OK - 59 api routes`).

---

## 10. Explicitly out of scope

- **Pre-existing bugs, not folded in unless asked:** the missing `category` / `inventory_2` menu
  icons (`sidenav.component.html` builds `/assets/menu_icons/<icon>`), and
  `topnav.component.ts:28` reading `localStorage.getItem('token')` when the real key is
  `STORAGE_KEYS.ACCESS_TOKEN` (`'app_accessToken'`). *The second one becomes a tenancy bug in
  Phase 7, so it will likely have to be fixed there anyway.*
- `material-module.ts` trimming (previously found unsafe to act on).
- `user.service.ts`'s 8 legacy methods against endpoints that no longer exist.
- Group-of-properties modelling — deferred until a chain actually appears.

---

## 11. Phases

| # | Phase | Status | Deliverable | Verified by |
|---|---|---|---|---|
| 1 | Tenant registry & resolution | **done** | `tenants`, `platform_users` models; `tenant_context`; `before_request` resolution; public tenant-info endpoint | App boots unchanged; `acme` resolves to a tenant; platform routes are skipped |
| 2 | Model scoping | **done** | `TenantScoped` mixin on every §3.3 model; composite constraints | Models import clean; migrations regenerated by hand |
| 3 | Enforcement | next | `do_orm_execute` filter, `before_flush` stamp + FK guard, leak audit script, leak tests | Cross-tenant read returns nothing; spike closes §5.3 |
| 4 | Auth integration | | `tenant_id` JWT claim on all token types; `authenticate()` cross-check; host-only refresh cookie; platform auth | Token A rejected on B; suspended tenant 403 |
| 5 | Provisioning | **done** (early — see §7) | Tenant-aware seeders; `provision_tenant()`; `seed_platform_data` / `seed_tenant_defaults` / `seed_tenant_demo_data` | Two tenants provisioned into a scratch DB, each isolated (see §9) |
| 6 | Per-tenant config & content | | Per-tenant `system_settings`, templates, branding, email `company_name`, upload paths | Two tenants send differently-branded mail |
| 7 | Frontend | | Tenant-aware `InstanceService`, `X-Tenant` header, per-tenant token key | Two tenants driven side by side in one browser |
| 8 | Verification & docs | | Full pass, leakage + request tests, this doc updated | All of §9 green |

Phase 3 is the one that decides whether this is safe. The leak test is written **first and made to
fail**, then the filter is added to make it pass.

> **Known broken window between Phase 2 and Phase 3.** `tenant_id` is `NOT NULL` with no default and
> nothing stamps it yet, so *writes* to tenant-scoped tables through the API fail with a NOT NULL
> violation until the `before_flush` stamp lands. Reads are unaffected. The **seeders are no longer
> affected**, because Phase 5's seeders set `tenant_id` explicitly instead of waiting to be stamped —
> which is also what let them be verified against a real database at this point. Do not run the app
> for real work against a migrated DB until Phase 3 is in.

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
