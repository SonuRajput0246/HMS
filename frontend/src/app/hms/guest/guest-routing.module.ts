import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListComponent } from './list/list.component';
import { AuthGuard } from '../../core/auth.guard';
import { ManageGuestComponent } from './manage-guest/manage-guest.component';

const routes: Routes = [
  {
    path: '',
    component: ListComponent,
    data: { menuId: 9 },
    canActivate: [AuthGuard]
  },
  {
    path: 'add-guest',
    component: ManageGuestComponent,
    data: { menuId: 9 },
    canActivate: [AuthGuard]
  },
  {
    path: 'update-guest/:id',
    component: ManageGuestComponent,
    data:{ menuId: 9 },
    canActivate: [AuthGuard]
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class GuestRoutingModule { }
