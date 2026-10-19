import { MatPaginatorSelectConfig } from '@angular/material/paginator';

/**
 * Shared config for the page-size ("Items per page") select that MatPaginator
 * builds into every list page's footer.
 *
 * `panelClass` tags the option list so the global stylesheet can size it: the
 * list is rendered inside the CDK overlay, i.e. outside any component's view,
 * so a component stylesheet could never reach it. `disableOptionCentering`
 * stops the panel from padding itself open to line the selected value up with
 * the trigger, so it wraps the options instead.
 *
 * Bound through `[selectConfig]` on every <mat-paginator> that offers a page
 * size, so the trigger and its option list stay the same size across pages.
 */
export const PAGE_SIZE_SELECT_CONFIG: MatPaginatorSelectConfig = {
  panelClass: 'compact-page-size-panel',
  disableOptionCentering: true
};