/**
 * The CMS navigation registry.
 *
 * Why this exists
 * ---------------
 * The CMS had no navigation at all. There is no layout component, no sidenav
 * and no topnav under src/app/cms, and not one `routerLink` in any CMS
 * template. The only way into a CMS screen was a button on the dashboard --
 * seven of them -- which left `orders` and `inventory` reachable only by typing
 * the address bar.
 *
 * The obvious fix, rendering `menu_access` directly the way HMS's sidenav does,
 * does not work. `menu_access` is built from `role_module_access` with no
 * instance filter, so a CMS user on Super Admin or Admin is handed Room,
 * Reservation, Guest, Folio and Housekeeping as well -- modules whose routes
 * exist only under /hms. And the CMS module seeder declares more modules than
 * the CMS has screens for: USER_MANAGEMENT, ROLE and TEMPLATE all have a
 * module row and a Create/Edit/Delete grant, but no CMS route exists for any
 * of them. A menu built straight from the access list would therefore be wrong
 * in both directions.
 *
 * So the menu is driven from this table instead, and `menu_access` only decides
 * which of these entries the signed-in role may see.
 */

/** One navigable destination in the CMS. */
export interface CmsMenuEntry {
  /** Matches Module.module_name from the CMS module seeder. */
  moduleName: string;

  /** Path relative to /cms. */
  path: string;

  /**
   * Whether the item stays highlighted on child routes.
   *
   * True for leaf screens such as /cms/orders. False for inventory, which is a
   * dashboard with children -- /cms/inventory/list-inventory should keep
   * Inventory highlighted rather than dropping the highlight.
   */
  exact: boolean;

  /**
   * Full-bleed screens sit outside the dashboard shell.
   *
   * POS and KDS are used continuously by a cashier and a chef, so the sidebar
   * and breadcrumb would eat vertical space they need. They are listed in the
   * menu because they have to be reachable, but the shell is not wrapped around
   * them -- see cms-routing.module.ts.
   */
  fullBleed?: boolean;
}

/** The shape cmsMenuFor needs from a menu_access row. */
export interface CmsMenuAccessLike {
  module_name: string;
  module_display_name?: string;
  icon?: string;
}

/**
 * A registry entry joined to the access row that granted it.
 *
 * The label and icon come from the database rather than from this file, so a
 * module renamed or re-iconed in the modules table shows the new wording
 * without a frontend change. Only the destination is defined here.
 */
export interface CmsMenuItem {
  entry: CmsMenuEntry;
  moduleName: string;
  displayName: string;
  /** Asset filename such as `dashboard.png`; empty when the module has none. */
  icon: string;
}

export const CMS_MENU: CmsMenuEntry[] = [
  { moduleName: 'DASHBOARD', path: 'dashboard', exact: true },
  { moduleName: 'POS', path: 'pos', exact: true, fullBleed: true },
  { moduleName: 'KDS', path: 'kds', exact: true, fullBleed: true },
  { moduleName: 'TABLE', path: 'tables', exact: true },
  { moduleName: 'ORDER', path: 'orders', exact: true },
  { moduleName: 'CUSTOMER', path: 'customers', exact: true },
  { moduleName: 'RECIPE', path: 'recipes', exact: true },
  { moduleName: 'INVENTORY_MANAGEMENT', path: 'inventory', exact: false },
  { moduleName: 'REPORTS', path: 'reports', exact: true },
];

/** Look up the destination for a module name, if this deployment has a screen for it. */
export function cmsMenuEntryFor(moduleName: string | null | undefined): CmsMenuEntry | undefined {
  if (!moduleName) {
    return undefined;
  }
  return CMS_MENU.find(entry => entry.moduleName === moduleName);
}

/**
 * Build the menu for a role.
 *
 * Anything whose module_name is not in CMS_MENU is dropped, which covers both
 * failure modes: another instance's modules, and this instance's modules that
 * have no screen.
 *
 * Keyed on module_name rather than module id for the same reason authorization
 * is: ids depend on the order the seeder happened to insert rows, while names
 * are declared in src/database/seeders/cms/module_seeder.py.
 *
 * Order follows CMS_MENU rather than display_order_no, because the two
 * disagree -- the seeder gives RECIPE order 9 and REPORTS order 12, but reports
 * is the last thing a cafe manager opens in a shift. CMS_MENU is the deliberate
 * ordering and this keeps one source of truth for it.
 */
export function cmsMenuFor<T extends CmsMenuAccessLike>(access: T[] | null | undefined): CmsMenuItem[] {
  if (!access?.length) {
    return [];
  }

  const byName = new Map<string, T>();
  for (const item of access) {
    byName.set(item.module_name, item);
  }

  const items: CmsMenuItem[] = [];
  for (const entry of CMS_MENU) {
    const grant = byName.get(entry.moduleName);
    if (!grant) {
      continue;
    }
    items.push({
      entry,
      moduleName: entry.moduleName,
      displayName: grant.module_display_name?.trim() || entry.moduleName,
      icon: grant.icon ?? '',
    });
  }
  return items;
}