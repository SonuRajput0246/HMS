import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { InventoryRoutingModule } from './inventory-routing.module';
import { ListCategoryComponent } from './list-category/list-category.component';
import { ManageCategoryComponent } from './manage-category/manage-category.component';
import { ListInventoryComponent } from './list-inventory/list-inventory.component';
import { ManageInventoryComponent } from './manage-inventory/manage-inventory.component';
import { InventoryDashboardComponent } from './inventory-dashboard/inventory-dashboard.component';
import { SharedModule } from '../../shared/shared.module';


/**
 * Inventory screens.
 *
 * These live under `hms/` by history, not by dependency: every one of them
 * talks only to InventoryService and shared models, with no hotel-specific
 * code. Inventory is genuinely shared -- the models, seeders and category/unit
 * reference data are all in `common/`, and on the CMS side
 * Recipe.calculate_cost_from_ingredients() prices every recipe line from
 * Inventory.unit_cost.
 *
 * The components are exported so the CMS route table can mount the same screens
 * under /cms/inventory. They cannot simply share this module's routing, because
 * InventoryRoutingModule hardcodes menuId 3, which is INVENTORY_MANAGEMENT in
 * HMS but TABLE in CMS -- a cafe user would have been granted access by holding
 * the table permission and refused access for holding the inventory one.
 */
@NgModule({
  declarations: [
    ListCategoryComponent,
    ManageCategoryComponent,
    ListInventoryComponent,
    ManageInventoryComponent,
    InventoryDashboardComponent
  ],
  imports: [
    CommonModule,
    InventoryRoutingModule,
    SharedModule
  ],
  exports: [
    ListCategoryComponent,
    ManageCategoryComponent,
    ListInventoryComponent,
    ManageInventoryComponent,
    InventoryDashboardComponent
  ]
})
export class InventoryModule { }
