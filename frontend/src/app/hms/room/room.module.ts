import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { RoomRoutingModule } from './room-routing.module';
import { ListRoomComponent } from './list-room/list-room.component';
import { SharedModule } from '../../shared/shared.module';
import { ManageRoomComponent } from './manage-room/manage-room.component';


@NgModule({
  declarations: [
    ListRoomComponent,
    ManageRoomComponent
  ],
  imports: [
    CommonModule,
    RoomRoutingModule,
    SharedModule
  ]
})
export class RoomModule { }
