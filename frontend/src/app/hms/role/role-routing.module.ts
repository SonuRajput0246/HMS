import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListComponent } from './list/list.component';
import { AuthGuard } from '../../core/auth.guard';
import { ManageRoleComponent } from './manage-role/manage-role.component';
import { ManageRoleAccessComponent } from './manage-role-access/manage-role-access.component';

const routes: Routes = [
  {
    path: '',
    component: ListComponent,
    data: { menuId: 8 },
    canActivate: [AuthGuard]
  },
  {
    path: 'add-role',
    component: ManageRoleComponent,
    data: { menuId: 8 },
    canActivate: [AuthGuard]
  },
  {
    path: 'update-role/:id',
    component: ManageRoleComponent,
    data:{ menuId: 8 },
    canActivate: [AuthGuard]
  },
  {
    path: 'manage-role-access/:id',
    component: ManageRoleAccessComponent,
    data:{ menuId: 8 },
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class RoleRoutingModule { }
