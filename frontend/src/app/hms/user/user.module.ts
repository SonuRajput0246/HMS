import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { UserRoutingModule } from './user-routing.module';
import { ListComponent } from './list/list.component';
import { ManageUserComponent } from './manage-user/manage-user.component';
import { SharedModule } from '../../shared/shared.module';


@NgModule({
  declarations: [
    ListComponent,
    ManageUserComponent
  ],
  imports: [
    CommonModule,
    UserRoutingModule,
    SharedModule
  ]
})
export class UserModule { }
