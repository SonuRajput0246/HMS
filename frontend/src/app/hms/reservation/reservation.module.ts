import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { ReservationRoutingModule } from './reservation-routing.module';
import { AvailableRoomComponent } from './available-room/available-room.component';
import { ListReservationComponent } from './list-reservation/list-reservation.component';
import { SharedModule } from '../../shared/shared.module';
import { GuestDetailsComponent } from './guest-details/guest-details.component';
import { AdvancePaymentComponent } from './advance-payment/advance-payment.component';
import { SelectGuestComponent } from './select-guest/select-guest.component';
import { ReservationDetailsComponent } from './reservation-details/reservation-details.component';
import { EditReservationComponent } from './edit-reservation/edit-reservation.component';


@NgModule({
  declarations: [
    AvailableRoomComponent,
    ListReservationComponent,
    GuestDetailsComponent,
    AdvancePaymentComponent,
    SelectGuestComponent,
    ReservationDetailsComponent,
    EditReservationComponent
  ],
  imports: [
    CommonModule,
    ReservationRoutingModule,
    SharedModule
  ]
})
export class ReservationModule { }
