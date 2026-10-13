import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { RoleRoutingModule } from './role-routing.module';
import { ListComponent } from './list/list.component';
import { ManageRoleComponent } from './manage-role/manage-role.component';
import { SharedModule } from '../../shared/shared.module';
import { ManageRoleAccessComponent } from './manage-role-access/manage-role-access.component';


@NgModule({
  declarations: [
    ListComponent,
    ManageRoleComponent,
    ManageRoleAccessComponent
  ],
  imports: [
    CommonModule,
    RoleRoutingModule,
    SharedModule
  ]
})
export class RoleModule { }
