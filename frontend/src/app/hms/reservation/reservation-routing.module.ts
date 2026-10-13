import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AvailableRoomComponent } from './available-room/available-room.component';
import { AuthGuard } from '../../core/auth.guard';
import { ListReservationComponent } from './list-reservation/list-reservation.component';
import { GuestDetailsComponent } from './guest-details/guest-details.component';
import { AdvancePaymentComponent } from './advance-payment/advance-payment.component';
import { SelectGuestComponent } from './select-guest/select-guest.component';
import { ReservationDetailsComponent } from './reservation-details/reservation-details.component';
import { EditReservationComponent } from './edit-reservation/edit-reservation.component';
const routes: Routes = [
  {
    path: '',
    component: ListReservationComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: 'available-rooms',
    component: AvailableRoomComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: 'select-guest',
    component: SelectGuestComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: 'guest-details',
    component: GuestDetailsComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: 'guest-details/:guestId',
    component: GuestDetailsComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: ':reservationId/advance-payment',
    component: AdvancePaymentComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    path: ':reservationId/reservation-details',
    component: ReservationDetailsComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  },
  {
    // Matches the URL the reservation-details Edit button already targets
    path: 'edit/:reservationId',
    component: EditReservationComponent,
    data: { menuId: 6 },
    canActivate: [AuthGuard]
  }

];
@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ReservationRoutingModule { }
