import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ListRoomComponent } from './list-room/list-room.component';
import { AuthGuard } from '../../core/auth.guard';
import { ManageRoomComponent } from './manage-room/manage-room.component';

const routes: Routes = [
  {
    path: '',
    component: ListRoomComponent,
    data: { menuId: 7 },
    canActivate: [AuthGuard]
  },
  {
    path: 'add-room',
    component: ManageRoomComponent,
    data: { menuId: 7 },
    canActivate: [AuthGuard]
  },
  {
    path: 'update-room/:id',
    component: ManageRoomComponent,
    data:{ menuId: 7 },
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class RoomRoutingModule { }
