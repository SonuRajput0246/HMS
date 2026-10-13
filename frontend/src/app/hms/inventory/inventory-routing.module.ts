import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { InventoryDashboardComponent } from './inventory-dashboard/inventory-dashboard.component';
import { AuthGuard } from '../../core/auth.guard';
import { ListCategoryComponent } from './list-category/list-category.component';
import { ManageCategoryComponent } from './manage-category/manage-category.component';
import { ListInventoryComponent } from './list-inventory/list-inventory.component';
import { ManageInventoryComponent } from './manage-inventory/manage-inventory.component';


// const routes: Routes = [
//   {
//     path: '',
//     component: InventoryDashboardComponent,
//     data: { menuId: 3 },
//     canActivate: [AuthGuard],
//     children: [
//       {
//         path: '',
//         redirectTo: 'list-category',
//         pathMatch: 'full'
//       },
//       {
//         path: 'list-category',
//         component: ListCategoryComponent,
//         data: { menuId: 3 }
//       },
//       {
//         path: 'manage-category',
//         component: ManageCategoryComponent,
//         data: { menuId: 3 }
//       },
//       {
//         path: 'list-inventory',
//         component: ListInventoryComponent,
//         data: { menuId: 3 }
//       },
//       {
//         path: 'manage-inventory',
//         component: ManageInventoryComponent,
//         data: { menuId: 3 }
//       }
//     ]
//   }
// ];





const routes: Routes = [
  {
    path: '',
    component: InventoryDashboardComponent,
    data: { menuId: 3, breadcrumb: 'Inventory Management' },
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
        data: { menuId: 3, breadcrumb: 'Category List' }
      },
      {
        path: 'add-category',
        component: ManageCategoryComponent,
        data: { menuId: 3, breadcrumb: 'Add Category' }
      },
      {
        path: 'update-category/:id',
        component: ManageCategoryComponent,
        data: { menuId: 3, breadcrumb: 'Edit Category' }
      },
      {
        path: 'list-inventory',
        component: ListInventoryComponent,
        data: { menuId: 3, breadcrumb: 'Inventory List' }
      },
      {
        path: 'add-inventory',
        component: ManageInventoryComponent,
        data: { menuId: 3, breadcrumb: 'Add Inventory' }
      },
      {
        path: 'update-inventory/:id',
        component: ManageInventoryComponent,
        data: { menuId: 3, breadcrumb: 'Edit Inventory' }
      }
    ]
  }
];


@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})  
export class InventoryRoutingModule { }
