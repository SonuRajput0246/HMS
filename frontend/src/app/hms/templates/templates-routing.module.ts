import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AuthGuard } from '../../core/auth.guard';
import { ListTemplateComponent } from './list/list.component';
import { ManageTemplateComponent } from './manage-template/manage-template.component';

/// menuId 10 is the TEMPLATE row added to module_seeder.py. AuthGuard compares
/// it against the signed-in user's menu_access, so these routes 404 until the
/// seeder has run.
const MENU_ID = 10;

const routes: Routes = [
  {
    path: '',
    component: ListTemplateComponent,
    data: { menuId: MENU_ID },
    canActivate: [AuthGuard]
  },
  {
    path: 'add-template',
    component: ManageTemplateComponent,
    data: { menuId: MENU_ID },
    canActivate: [AuthGuard]
  },
  {
    path: 'update-template/:id',
    component: ManageTemplateComponent,
    data: { menuId: MENU_ID },
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class TemplatesRoutingModule { }