import { Route } from '@angular/router';

import { CMS_MENU, cmsMenuFor, cmsMenuEntryFor } from './cms-menu';
import { routes as cmsRoutes } from './cms-routing.module';

/**
 * The registry is what makes the CMS menu trustworthy, so it is tested against
 * the three ways it can be wrong: leaking another instance's modules, offering
 * a module with no screen behind it, and ordering by something other than the
 * deliberate list.
 */
describe('cms menu registry', () => {

  /** A menu_access row, as the login response builds it. */
  function access(moduleName: string, over: Record<string, unknown> = {}) {
    return {
      module_id: 1,
      module_name: moduleName,
      module_display_name: moduleName.replace(/_/g, ' ').toLowerCase(),
      menu_parent_code: 0,
      icon: `${moduleName.toLowerCase()}.png`,
      route_path: moduleName.toLowerCase(),
      has_child_menu: false,
      accessList: [],
      ...over,
    };
  }

  describe('cmsMenuFor', () => {

    it('returns nothing for a role with no modules', () => {
      expect(cmsMenuFor([])).toEqual([]);
      expect(cmsMenuFor(null)).toEqual([]);
      expect(cmsMenuFor(undefined)).toEqual([]);
    });

    it('keeps the modules the role holds that have a CMS screen', () => {
      const menu = cmsMenuFor([access('DASHBOARD'), access('ORDER')]);

      expect(menu.map(item => item.moduleName)).toEqual(['DASHBOARD', 'ORDER']);
    });

    /**
     * The whole point of the registry.
     *
     * menu_access is built from role_module_access with no instance filter, so
     * a CMS user on Super Admin is handed the hotel's modules too. Rendering
     * the access list directly -- as hms/layout/sidenav does -- put Room,
     * Reservation, Guest, Folio and Housekeeping in the cafe menu, every one
     * of them a dead link into a canMatch-gated tree.
     */
    it('drops modules that belong to the other instance', () => {
      const menu = cmsMenuFor([
        access('DASHBOARD'),
        access('ROOM'),
        access('RESERVATIONS'),
        access('GUEST'),
        access('FOLIO'),
        access('HOUSEKEEPING'),
      ]);

      expect(menu.map(item => item.moduleName)).toEqual(['DASHBOARD']);
      expect(menu.some(item => item.moduleName === 'ROOM')).toBe(false);
    });

    /**
     * Also a real gap rather than a hypothetical one.
     *
     * The CMS module seeder declares USER_MANAGEMENT, ROLE and TEMPLATE and
     * grants them Create/Edit/Delete, but the CMS has no route for any of them.
     * A menu built from the access list would offer three links that 404.
     */
    it('drops modules that this instance declares but has no screen for', () => {
      const menu = cmsMenuFor([
        access('DASHBOARD'),
        access('USER_MANAGEMENT'),
        access('ROLE'),
        access('TEMPLATE'),
      ]);

      expect(menu.map(item => item.moduleName)).toEqual(['DASHBOARD']);
    });

    /// Child modules are reached through their parent's screen, not as
    /// top-level rows. INVENTORY_CATEGORY's route_path is 'inventory/categories'
    /// but no such route exists.
    it('drops child modules, which are reached through the parent', () => {
      const menu = cmsMenuFor([
        access('INVENTORY_MANAGEMENT'),
        access('INVENTORY_CATEGORY'),
        access('INVENTORY_ITEM'),
        access('RECIPE_ITEM'),
        access('RECIPE_CATEGORY'),
      ]);

      expect(menu.map(item => item.moduleName)).toEqual(['INVENTORY_MANAGEMENT']);
    });

    it('orders by the registry, not by display_order_no', () => {
      const menu = cmsMenuFor([
        // Deliberately out of order, and claiming to be first.
        access('REPORTS', { display_order_no: 0 }),
        access('ORDER', { display_order_no: 99 }),
        access('DASHBOARD', { display_order_no: 50 }),
      ]);

      expect(menu.map(item => item.moduleName)).toEqual([
        'DASHBOARD', 'ORDER', 'REPORTS',
      ]);
    });

    it('takes the label and icon from the database, not from the registry', () => {
      const menu = cmsMenuFor([
        access('ORDER', { module_display_name: 'Ring Up', icon: 'receipt_long.png' }),
      ]);

      expect(menu[0].displayName).toBe('Ring Up');
      expect(menu[0].icon).toBe('receipt_long.png');
    });

    it('falls back to the module name when the row carries no display name', () => {
      const menu = cmsMenuFor([access('ORDER', { module_display_name: '   ' })]);

      expect(menu[0].displayName).toBe('ORDER');
    });

    it('tolerates a row with no icon', () => {
      const menu = cmsMenuFor([access('ORDER', { icon: undefined })]);

      expect(menu[0].icon).toBe('');
    });

    it('collapses a duplicate grant to a single row', () => {
      const menu = cmsMenuFor([access('ORDER'), access('ORDER')]);

      expect(menu.length).toBe(1);
    });
  });

  describe('cmsMenuEntryFor', () => {
    it('finds a registered module', () => {
      expect(cmsMenuEntryFor('ORDER')?.path).toBe('orders');
    });

    it('returns nothing for an unregistered, absent or empty name', () => {
      expect(cmsMenuEntryFor('ROOM')).toBeUndefined();
      expect(cmsMenuEntryFor(null)).toBeUndefined();
      expect(cmsMenuEntryFor(undefined)).toBeUndefined();
      expect(cmsMenuEntryFor('')).toBeUndefined();
    });
  });

  describe('the registry itself', () => {

    /**
     * Drift guard.
     *
     * The registry and the route table are two hand-maintained lists describing
     * the same thing. If they drift, the menu starts producing dead links --
     * which is exactly the bug the registry was introduced to remove. Asserting
     * them against each other here means a new screen added to one and not the
     * other fails in CI rather than at runtime.
     */
    it('points every entry at a path the CMS route table actually serves', () => {
      const served = new Set<string>();
      const collect = (list: Route[]) => {
        for (const route of list) {
          const path = route.path;
          if (route.children?.length) {
            // Recurse before skipping an empty path: the shell route is
            // `path: ''` and every admin screen hangs off it.
            if (path) {
              served.add(path);
            }
            collect(route.children);
          } else if (path && !path.includes(':') && path !== '**') {
            served.add(path);
          }
        }
      };
      collect(cmsRoutes);

      for (const entry of CMS_MENU) {
        expect(served)
          .withContext(`${entry.moduleName} points at '${entry.path}', which no CMS route serves`)
          .toContain(entry.path);
      }
    });

    /// The other direction: a screen the route table serves but the menu never
    /// offers. That is how orders and inventory ended up unreachable in the
    /// first place, so it is worth failing on.
    it('covers every top-level screen the route table serves', () => {
      const shell = cmsRoutes.find(route => route.children?.length);
      const screens = (shell?.children ?? [])
        .filter(route => route.path && !route.path.includes(':') && route.path !== '')
        .map(route => route.path as string);

      // pos and kds are routed outside the shell, at the top level.
      const topLevel = cmsRoutes
        .filter(route => route.path && !route.children?.length && route.path !== '**')
        .map(route => route.path as string);

      const menuPaths = new Set(CMS_MENU.map(entry => entry.path));
      const uncovered = [...screens, ...topLevel].filter(path => !menuPaths.has(path));

      expect(uncovered)
        .withContext('these CMS screens are routed but absent from the menu')
        .toEqual([]);
    });

    it('marks inventory as non-exact so child routes keep it highlighted', () => {
      const inventory = cmsMenuEntryFor('INVENTORY_MANAGEMENT');

      // /cms/inventory is a dashboard whose children are /list-category,
      // /list-inventory, /add-inventory and /update-inventory/:id. Exact
      // matching would drop the highlight on all of them.
      expect(inventory?.exact).toBe(false);
    });

    it('flags pos and kds as full-bleed', () => {
      expect(cmsMenuEntryFor('POS')?.fullBleed).toBe(true);
      expect(cmsMenuEntryFor('KDS')?.fullBleed).toBe(true);
      expect(cmsMenuEntryFor('ORDER')?.fullBleed).toBeUndefined();
    });

    it('has no duplicate module names', () => {
      const names = CMS_MENU.map(entry => entry.moduleName);

      expect(new Set(names).size).toBe(names.length);
    });
  });
});