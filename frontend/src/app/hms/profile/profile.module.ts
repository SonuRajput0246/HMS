import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { ProfileRoutingModule } from './profile-routing.module';
import { ViewProfileComponent } from './view-profile/view-profile.component';
import { ManageProfileComponent } from './manage-profile/manage-profile.component';
import { SharedModule } from '../../shared/shared.module';


@NgModule({
  declarations: [
    ViewProfileComponent,
    ManageProfileComponent
  ],
  imports: [
    CommonModule,
    ProfileRoutingModule,
    SharedModule
  ]
})
export class ProfileModule { }
