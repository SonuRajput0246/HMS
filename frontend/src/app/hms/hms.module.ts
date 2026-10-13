import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { HmsRoutingModule } from './hms-routing.module';
import { SharedModule } from '../shared/shared.module';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { LayoutComponent } from './layout/layout.component';
import { SidenavComponent } from './layout/sidenav/sidenav.component';
import { TopnavComponent } from './layout/topnav/topnav.component';


@NgModule({
  declarations: [
    LayoutComponent,
    SidenavComponent,
    TopnavComponent,
  ],
  imports: [
    CommonModule,
    HmsRoutingModule,
    SharedModule,
    RouterModule,
    MatCardModule
  ]
})
export class HmsModule { }
