import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { SharedModule } from '../../shared/shared.module';
import { InventoryModule } from '../../hms/inventory/inventory.module';
import { CmsInventoryRoutingModule } from './cms-inventory-routing.module';

/**
 * Mounts the shared inventory screens under /cms/inventory.
 *
 * InventoryModule is imported purely for component scope. The screens are
 * declared there and exported; Angular resolves a route's `component` from the
 * enclosing module's compilation scope, which includes exported declarations of
 * imported modules, so re-declaring them here would be an error rather than a
 * convenience. SharedModule is still imported because it carries the Material
 * and form directives the screens' templates rely on.
 *
 * Routing lives in CmsInventoryRoutingModule because the menuIds differ per
 * instance -- see the note there.
 */
@NgModule({
  imports: [
    CommonModule,
    SharedModule,
    InventoryModule,
    CmsInventoryRoutingModule
  ]
})
export class CmsInventoryModule { }