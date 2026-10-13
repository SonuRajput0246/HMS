import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AuthGuard } from '../../core/auth.guard';
import { InventoryDashboardComponent } from '../../hms/inventory/inventory-dashboard/inventory-dashboard.component';
import { ListCategoryComponent } from '../../hms/inventory/list-category/list-category.component';
import { ManageCategoryComponent } from '../../hms/inventory/manage-category/manage-category.component';
import { ListInventoryComponent } from '../../hms/inventory/list-inventory/list-inventory.component';
import { ManageInventoryComponent } from '../../hms/inventory/manage-inventory/manage-inventory.component';

/**
 * Inventory routes for the cafe product.
 *
 * Duplicates the shape of hms/inventory/inventory-routing.module.ts rather
 * than reusing it, and that duplication is the whole point. That module
 * hardcodes `menuId: 3`, which is INVENTORY_MANAGEMENT in the HMS module seeder
 * but TABLE in the CMS one. Mounting it here would mean AuthGuard checked the
 * signed-in cafe user's access to the *table* module: anyone holding TABLE could
 * walk into stock control, and anyone holding INVENTORY_ITEM would be refused
 * entry to the very screens it grants.
 *
 * menuIds here are the CMS module seeder's (src/database/seeders/cms/
 * module_seeder.py), and they track the seeder's own granularity rather than
 * collapsing everything onto the parent:
 *
 *   8  INVENTORY_MANAGEMENT  the section itself
 *   9  INVENTORY_CATEGORY    category screens
 *   10 INVENTORY_ITEM        item screens
 *
 * MANAGER holds Create/Edit/View on 9 and 10 but only View on 8, so the
 * section gate admits a manager and the per-screen gates are what actually
 * decide whether they can change anything.
 *
 * The components are imported from the hms/ folder because they are shared and
 * have no hotel-specific behaviour. If that ever stops being true, these files
 * are the ones to move rather than the components.
 */
const routes: Routes = [
  {
    path: '',
    component: InventoryDashboardComponent,
    data: { menuId: 8, breadcrumb: 'Inventory Management' },
    canActivate: [AuthGuard],
    children: [
      {
        path: '',
        redirectTo: 'list-category',
        pathMatch: 'full'
      },
      {
        path: 'list-category',
        component: ListCategoryComponent,
        data: { menuId: 9, breadcrumb: 'Category List' }
      },
      {
        path: 'add-category',
        component: ManageCategoryComponent,
        data: { menuId: 9, breadcrumb: 'Add Category' }
      },
      {
        path: 'update-category/:id',
        component: ManageCategoryComponent,
        data: { menuId: 9, breadcrumb: 'Edit Category' }
      },
      {
        path: 'list-inventory',
        component: ListInventoryComponent,
        data: { menuId: 10, breadcrumb: 'Inventory List' }
      },
      {
        path: 'add-inventory',
        component: ManageInventoryComponent,
        data: { menuId: 10, breadcrumb: 'Add Inventory' }
      },
      {
        path: 'update-inventory/:id',
        component: ManageInventoryComponent,
        data: { menuId: 10, breadcrumb: 'Edit Inventory' }
      }
    ]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class CmsInventoryRoutingModule { }