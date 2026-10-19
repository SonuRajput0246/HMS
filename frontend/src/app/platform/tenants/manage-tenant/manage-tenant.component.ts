import { Component, OnDestroy, inject } from '@angular/core';
import { FormBuilder, FormControl, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subscription, forkJoin } from 'rxjs';
import { finalize } from 'rxjs/operators';

import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IEntityResponse } from '../../../models/ICommon.model';
import { IAuditLog, ICurrencyOption, ITenant, ITimezoneOption } from '../../models/platform.model';
import { PlatformAuditService } from '../../services/platform-audit.service';
import { PlatformConfigService } from '../../services/platform-config.service';
import { PlatformLookupService } from '../../services/platform-lookup.service';
import { PlatformTenantService } from '../../services/platform-tenant.service';

/** Mirrors the backend's SLUG_REGEX exactly -- see tenant_management_schema.py. */
const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

/** The name column is 150 wide; the server enforces the same window. */
const NAME_MAX = 150;

/**
 * One screen for both halves of a create -- the hotel and its first
 * administrator -- and for the (necessarily narrower) edit, where the admin
 * fields are absent because the backend does not accept them there.
 *
 * Client-side rules restate the server's rather than replace them: the same
 * regex, the same 6..20 password window. The server remains the authority; a
 * mismatch only decides whether the browser warns first or the API does.
 *
 * Timezone and currency are picked from lists the server supplies, not typed.
 * They used to be free-text inputs with a small hardcoded suggestion list, so
 * the "dropdown" could offer a currency that does not exist and always offered
 * the same seven zones. Now the options are the real `currencies` rows and the
 * same IANA zones `ZoneInfo` accepts on save, so what the picker shows and what
 * the server accepts cannot disagree.
 */
@Component({
  selector: 'app-manage-tenant',
  templateUrl: './manage-tenant.component.html',
  styleUrl: './manage-tenant.component.scss',
})
export class ManageTenantComponent implements OnDestroy {

  private fb = inject(FormBuilder);
  private _route = inject(ActivatedRoute);
  private _router = inject(Router);
  private _tenants = inject(PlatformTenantService);
  private _lookups = inject(PlatformLookupService);
  private _config = inject(PlatformConfigService);
  private _audit = inject(PlatformAuditService);
  private _snackbar = inject(CustomSnackbarService);

  form!: FormGroup;
  tenantId: number | null = null;
  isLoading = false;
  isSaving = false;
  isLookupsLoading = false;

  /** This tenant's own audit trail, newest first. Populated only when editing,
   * since a brand-new tenant has no history to show. */
  tenantHistory: IAuditLog[] = [];
  isHistoryLoading = false;
  historyTotal = 0;

  /** Every active currency, and the subset currently shown after filtering. */
  currencyOptions: ICurrencyOption[] = [];
  filteredCurrencies: ICurrencyOption[] = [];

  /** Every IANA zone, and the subset currently shown after filtering. */
  timezoneOptions: ITimezoneOption[] = [];
  filteredTimezones: ITimezoneOption[] = [];

  /**
   * Search terms for the two pickers. Held outside the form: they filter what
   * is offered, they are not values the tenant has.
   */
  readonly currencyFilter = new FormControl('', { nonNullable: true });
  readonly timezoneFilter = new FormControl('', { nonNullable: true });

  private subs = new Subscription();

  get isEdit(): boolean {
    return this.tenantId !== null;
  }

  /**
   * The host this hotel will be served from, recomputed as the slug is typed.
   * The subdomain is the hotel's real identity, so showing its consequence next
   * to the field is the difference between "a slug" and "a URL people will use".
   *
   * The domain comes from the deployment rather than from a literal here: the
   * form's job is to show what the operator's own install will do with the
   * slug, and only the server knows that.
   */
  get tenantHost(): string {
    const slug = String(this.form?.get('slug')?.value ?? '').trim().toLowerCase();
    return this._config.tenantHost(slug);
  }

  /** The same domain, shown as the field's suffix. */
  get hostSuffix(): string {
    return this._config.tenantHostSuffix;
  }

  ngOnInit(): void {
    const idParam = this._route.snapshot.paramMap.get('id');
    this.tenantId = idParam ? Number(idParam) : null;

    this.buildForm();
    this.watchFilters();

    if (this.tenantId !== null) {
      /**
       * Sequencing, not aesthetics: the stored values are patched into the form
       * only once the options exist. A select asked to display a value whose
       * option has not rendered yet shows an empty field until the panel is
       * reopened -- see the same note in manage-template.
       */
      this.loadLookups(() => this.loadTenant(this.tenantId as number));
    } else {
      this.loadLookups();
    }
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }

  private buildForm(): void {
    const controls: Record<string, unknown> = {
      name: ['', [Validators.required, Validators.maxLength(NAME_MAX)]],
      slug: [
        '',
        [
          Validators.required,
          Validators.minLength(2),
          Validators.maxLength(63),
          Validators.pattern(SLUG_PATTERN),
        ],
      ],
      timezone: ['', [Validators.required, Validators.maxLength(50)]],
      currency: ['', [Validators.required, Validators.pattern(/^[A-Za-z]{3}$/)]],
    };

    if (!this.isEdit) {
      controls['admin_first_name'] = ['', [Validators.required, Validators.maxLength(50)]];
      controls['admin_last_name'] = ['', [Validators.required, Validators.maxLength(50)]];
      controls['admin_email'] = [
        '',
        [Validators.required, Validators.email, Validators.maxLength(255)],
      ];
      controls['admin_password'] = [
        '',
        [Validators.required, Validators.minLength(6), Validators.maxLength(20)],
      ];
    }

    this.form = this.fb.group(controls);
  }

  /** Re-filter a picker whenever its search box changes. */
  private watchFilters(): void {
    this.subs.add(
      this.currencyFilter.valueChanges.subscribe((term) => {
        this.filteredCurrencies = this.matchCurrencies(term);
      })
    );
    this.subs.add(
      this.timezoneFilter.valueChanges.subscribe((term) => {
        this.filteredTimezones = this.matchTimezones(term);
      })
    );
  }

  /**
   * Load the reference data both pickers draw from.
   *
   * A failure here is not fatal to an edit -- the stored values are still shown
   * and can be re-saved untouched -- but it leaves a new tenant unable to pick
   * a currency or zone, so it is reported rather than swallowed. `then` runs
   * either way, so an edit is never trapped behind a failed lookup.
   */
  private loadLookups(then?: () => void): void {
    this.isLookupsLoading = true;

    forkJoin({
      currencies: this._lookups.currencies(),
      timezones: this._lookups.timezones(),
    })
      .pipe(finalize(() => (this.isLookupsLoading = false)))
      .subscribe({
        next: ({ currencies, timezones }) => {
          this.currencyOptions = (currencies?.data as ICurrencyOption[]) ?? [];
          this.timezoneOptions = (timezones?.data as ITimezoneOption[]) ?? [];
          this.filteredCurrencies = [...this.currencyOptions];
          this.filteredTimezones = [...this.timezoneOptions];
          then?.();
        },
        error: () => {
          this._snackbar.openSnackBar(
            'Could not load the currency and timezone lists.',
            'error'
          );
          then?.();
        },
      });
  }

  private matchCurrencies(term: string): ICurrencyOption[] {
    const needle = (term || '').trim().toLowerCase();
    if (!needle) {
      return [...this.currencyOptions];
    }
    return this.currencyOptions.filter(
      (option) =>
        option.code.toLowerCase().includes(needle) ||
        (option.name || '').toLowerCase().includes(needle)
    );
  }

  private matchTimezones(term: string): ITimezoneOption[] {
    const needle = (term || '').trim().toLowerCase();
    if (!needle) {
      return [...this.timezoneOptions];
    }
    return this.timezoneOptions.filter((option) =>
      option.name.toLowerCase().includes(needle)
    );
  }

  /** `INR - Indian Rupee (₹)`, so the option says what the code means. */
  currencyLabel(option: ICurrencyOption): string {
    const symbol = option.symbol ? ` (${option.symbol})` : '';
    return `${option.code} - ${option.name}${symbol}`;
  }

  private loadTenant(id: number): void {
    this.isLoading = true;
    this._tenants.get(id)
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          const tenant = resp?.data as ITenant | null;
          if (!tenant) {
            return;
          }
          this.form.patchValue({
            name: tenant.name,
            slug: tenant.slug,
            timezone: tenant.timezone,
            currency: tenant.currency,
          });
          this.loadHistory();
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not load the tenant.',
            'error'
          );
          this.goBack();
        },
      });
  }

  /**
   * The newest few audit rows for this tenant, so the edit screen shows what has
   * already happened to it without leaving the page. Supplementary: a failure
   * here is swallowed rather than raising a snackbar, because it must never
   * block editing the tenant itself.
   */
  private loadHistory(): void {
    if (this.tenantId === null) {
      return;
    }
    this.isHistoryLoading = true;
    this._audit.list({
      page_size: 6,
      page_number: 1,
      entity_type: 'tenant',
      entity_id: this.tenantId,
    })
      .pipe(finalize(() => (this.isHistoryLoading = false)))
      .subscribe({
        next: (resp: IEntityResponse) => {
          this.tenantHistory = (resp?.data as IAuditLog[]) ?? [];
          this.historyTotal = resp?.meta?.total_records ?? 0;
        },
        error: () => {
          this.tenantHistory = [];
          this.historyTotal = 0;
        },
      });
  }

  /** Opens the full feed, already scoped to this tenant. */
  viewFullHistory(): void {
    this._router.navigate(['/platform/activity'], {
      queryParams: { entity_type: 'tenant', entity_id: this.tenantId },
    });
  }

  /** One-line summary of a row's `details`, for the compact list. */
  historySummary(log: IAuditLog): string {
    if (!log.details) {
      return '';
    }
    try {
      const parsed = JSON.parse(log.details);
      if (parsed && typeof parsed === 'object') {
        if (parsed.changed) {
          return Object.keys(parsed.changed).join(', ');
        }
        return Object.keys(parsed).join(', ');
      }
      return String(parsed);
    } catch {
      return log.details;
    }
  }

  save(): void {
    if (this.form.invalid || this.isSaving) {
      this.form.markAllAsTouched();
      return;
    }

    const value = this.form.value;
    this.isSaving = true;

    const request$: Observable<IEntityResponse> = this.isEdit
      ? this._tenants.update(this.tenantId as number, {
          name: value.name,
          slug: value.slug,
          timezone: value.timezone,
          currency: value.currency,
        })
      : this._tenants.create({
          name: value.name,
          slug: value.slug,
          timezone: value.timezone,
          currency: value.currency,
          admin_first_name: value.admin_first_name,
          admin_last_name: value.admin_last_name,
          admin_email: value.admin_email,
          admin_password: value.admin_password,
        });

    request$
      .pipe(finalize(() => (this.isSaving = false)))
      .subscribe({
        next: (resp) => {
          this._snackbar.openSnackBar(resp?.message || 'Saved.', 'success');
          this.goBack();
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'Could not save the tenant.',
            'error'
          );
        },
      });
  }

  goBack(): void {
    this._router.navigate(['/platform/tenants']);
  }
}
