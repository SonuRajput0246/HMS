import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { GuestRoutingModule } from './guest-routing.module';
import { ListComponent } from './list/list.component';
import { ManageGuestComponent } from './manage-guest/manage-guest.component';
import { SharedModule } from '../../shared/shared.module';


@NgModule({
  declarations: [
    ListComponent,
    ManageGuestComponent
  ],
  imports: [
    CommonModule,
    GuestRoutingModule,
    SharedModule
  ]
})
export class GuestModule { }
