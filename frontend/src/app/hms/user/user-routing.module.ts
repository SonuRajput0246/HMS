import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListComponent } from './list/list.component';
// import { RouteGuardService } from '../../services/route-guard.service';
import { ManageUserComponent } from './manage-user/manage-user.component';
import { AuthGuard } from '../../core/auth.guard';

const routes: Routes = [
  {
    path: '',
    component: ListComponent,
    data: { menuId: 2 },
    canActivate: [AuthGuard]
  },
  {
    path: 'add-user',
    component: ManageUserComponent,
    data: { menuId: 2 },
    canActivate: [AuthGuard]
  },
  {
    path: 'update-user/:id',
    component: ManageUserComponent,
    data:{menuId: 2},
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class UserRoutingModule { }
