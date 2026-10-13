import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ViewProfileComponent } from './view-profile/view-profile.component';
import { ManageProfileComponent } from './manage-profile/manage-profile.component';
import { AuthGuard } from '../../core/auth.guard';

const routes: Routes = [
  {
    // read-only profile display
    path: '',
    component: ViewProfileComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  },
  {
    // editable profile form
    path: 'edit',
    component: ManageProfileComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ProfileRoutingModule { }
