import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { TemplatesRoutingModule } from './templates-routing.module';
import { ListTemplateComponent } from './list/list.component';
import { ManageTemplateComponent } from './manage-template/manage-template.component';
import { SharedModule } from '../../shared/shared.module';

@NgModule({
  declarations: [
    ListTemplateComponent,
    ManageTemplateComponent
  ],
  imports: [
    CommonModule,
    TemplatesRoutingModule,
    SharedModule
  ]
})
export class TemplatesModule { }