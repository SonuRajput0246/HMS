# CMS Frontend — Build Spec

Read this fully before writing code. It exists so every screen is built the
same way; deviate only with a reason.

## Files that ALREADY EXIST — read these, do not recreate

| Path | What it gives you |
|---|---|
| `src/app/models/ICms.model.ts` | Every interface + the label maps (`STATION_LABELS`, `TABLE_STATUS_LABELS`, `PREP_STATUS_LABELS`, `ORDER_STATUS_LABELS`, `PAYMENT_METHOD_LABELS`) and `toAmount()` |
| `src/app/cms/cms-theme.scss` | SCSS tokens: `$navy $teal $page-bg $card-bg $border $text $text-muted $radius $shadow-card $ok $warn $danger $info $neutral` (+ `-soft` variants), mixins `cms-shell() cms-card() cms-page-bg() cms-scroll() cms-pill()`, maps `$table-status-colors $prep-status-colors $order-status-colors`, fn `status-pair($map,$key)` |
| `src/app/services/cms/floor.service.ts` | `CmsFloorService` — tables, zones, customers |
| `src/app/services/cms/recipe.service.ts` | `CmsRecipeService` — recipes, categories, ingredients, menu, stations |
| `src/app/services/cms/order.service.ts` | `CmsOrderService` — order lifecycle + `getBill` + `getSummary` |
| `src/app/services/cms/kds.service.ts` | `CmsKdsService` — kitchen board |
| `src/app/services/cms/report.service.ts` | `CmsReportService` — the six reports |
| `src/app/pipes/currency-inr.pipe.ts` | `currencyInr` pipe (declared+exported by `SharedModule`) |

## How to consume the theme

Stylesheets are **not** namespaced by Angular, so two components declaring the
same class name would collide. Prefix every top-level class with the screen
initials, e.g. `.pos-shell`, `.kds-shell`, `.tbl-list`, `.rpt-shell`.

```scss
@use '../cms-theme' as theme;   // ONE level up: theme sits in src/app/cms/
```

## Hard rules

1. **Never hand-roll a request.** Call the injected service. No `fetch`, no
   `HttpClient` in a component.
2. **Money stays a string** until the template. Use the `currencyInr` pipe, or
   `toAmount()` from the model file for arithmetic. Never `parseFloat` inline.
3. **The acting user is never a form field.** Do not add a `user_id` input.
4. **Never swallow an error.** Every subscribe needs both `next` and `error`;
   show the message via `CustomSnackbarService`.
5. **`isPageLoad = true`** before a fetch, `false` in `finalize()`.
6. Comments explain **why**, not what. The codebase already has this style —
   read `src/app/hms/inventory/inventory-dashboard/inventory-dashboard.component.ts`
   and `../../models/ICms.model.ts` to match the voice. Do not write
   `// increment counter`; write why the increment is safe.

## Component pattern

```ts
@Component({
  selector: 'app-pos-screen',
  templateUrl: './pos-screen.component.html',
  styleUrl: './pos-screen.component.scss'
})
export class PosScreenComponent implements OnInit {
  private _orderService = inject(CmsOrderService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);

  isPageLoad = false;
  // ... state

  ngOnInit(): void { this.load(); }

  private load(): void {
    this.isPageLoad = true;
    this._orderService.getFloorView()
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) { /* assign */ }
          else { this._snackbar.openSnackBar(res?.message || 'Failed to load', 'error'); }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'Something went wrong', 'error')
      });
  }
}
```

Each component needs **three** files: `.ts`, `.html`, `.scss`.

## Visual reference

`src/app/hms/inventory/` is the house style — navy `#003366`, teal accent,
white cards on a soft radial-gradient page, pill tabs, `mat-table` inside a
`.table-card` with a `.table-header` / `.table-scroll` / `.table-footer` layout,
`app-page-loader` overlay while loading, `app-navigation-bar` for breadcrumbs.

## Backend facts worth knowing

- **All money fields are strings.** `total_amount: "403.00"`.
- **Order statuses:** pending → confirmed → preparing → ready → served →
  completed. Cancelled is terminal.
- **Prep statuses:** pending → preparing → ready. `pending → ready` is allowed
  directly (one-tap KDS). voided is server-set only.
- **`is_available` on a recipe is the 86 switch** — separate from `is_active`,
  which is admin lifecycle.
- **A table has at most ONE open order.** `createOrder` 409s with
  `data.existing_order_id` when one exists — open *that* instead of erroring.
- **Closing an unpaid order 409s.** Use `closeOrder(id, {complete_payment:true,
  payment_method})` to settle and close in one call.
- **A void needs a reason** — use `ConfirmationService.confirmWithReason()`,
  which already exists and validates the input.
- **Report `range`** is a preset string (`today`, `last_7_days`, …) or
  `custom` + `from_date`/`to_date`. All dates are trading-timezone; the
  response echoes `range` metadata.
- **`kitchen_outstanding`** on a bill is the count of lines not yet plated.