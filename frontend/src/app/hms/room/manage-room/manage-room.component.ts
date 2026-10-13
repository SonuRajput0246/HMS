import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RoomService } from '../../../services/room.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ActivatedRoute, Router } from '@angular/router';
import { IEnumOption, INavigationaBar } from '../../../models/ICommon.model';
import { finalize } from 'rxjs/operators';
import { IRoomType } from '../../../models/IReservation.model';

@Component({
  selector: 'app-manage-room',
  templateUrl: './manage-room.component.html',
  styleUrl: './manage-room.component.scss'
})
export class ManageRoomComponent {

  private fb = inject(FormBuilder);
  private _roomService = inject(RoomService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);

  navData: INavigationaBar[] = [];
  roomForm!: FormGroup;
  breakpoint = 3;

  roomTypesList: IRoomType[] = [];
  isRoomTypeLoading = false;

  roomStatusList: IEnumOption[] = [];
  isRoomStatusLoading = false;
  
  isLoading = false;
  isPageLoad = false;
  
  roomObj: any = { id: 0 };
  isEditMode = false;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.onResize();
    this.fetchRoomTypes();
    this.fetchRoomStatuses();

    const roomId = Number(this.AR.snapshot.paramMap.get('id'));
    if (roomId) {
      this.isEditMode = true;
      this.GetRoomById(roomId);
      this.navData = [
        ...this.navData,
        { displayValue: 'Edit Room', isClickable: false, isDashboard: false }
      ];
    } else {
      this.navData = [
        ...this.navData,
        { displayValue: 'Add Room', isClickable: false, isDashboard: false }
      ]
    }
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Room Management', isClickable: true, isDashboard: false, redirectValue: '/hms/rooms' }
    ];
  }

  private createForm(): void {
    this.roomForm = this.fb.group({
      room_number: ['', Validators.required],
      room_type_id: [null, Validators.required],
      floor_number: [null, Validators.required],
      room_status: ['', Validators.required],
      view: [''],
      notes: [''],
      is_active: [true]
    });
  }

  onResize(): void {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }

  fetchRoomStatuses(): void {
    this.isRoomStatusLoading = true;
    this._roomService.getEnumOptions('room_status')
      .pipe(finalize(() => this.isRoomStatusLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roomStatusList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch room statuses', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching room statuses';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }


  insertUpdateRoom(): void {
    if (this.roomForm.invalid) {
      this.roomForm.markAllAsTouched();
      return;
    }
    const payload = {
      ...this.roomForm.value,
      id: this.roomObj?.id || 0,
      is_deleted: false
    };
    this.isLoading = true;
    this._roomService.insertUpdateRoom(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Room saved successfully', "success");
            this._router.navigate(['/hms/rooms']);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save room', "error");
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving room';
          this._snackbar.openSnackBar(msg, "error");
        }
      });
  }


  GetRoomById(roomId: number) {
    if (roomId > 0) {
      this.isPageLoad = true;
      this._roomService.getRoomById(roomId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.isEditMode = true;
              this.roomObj = res.data;

              this.roomForm.patchValue({
                id: this.roomObj.id,
                room_number: this.roomObj.room_number,
                room_type_id: this.roomObj.room_type_id,
                floor_number: this.roomObj.floor_number,
                room_status: this.roomObj.room_status,
                view: this.roomObj.view,
                notes: this.roomObj.notes,
                is_active: this.roomObj.is_active
              });
              // this.roomForm.get('room_number')?.disable();
              // this.roomForm.get('room_type_id')?.disable();
              // this.roomForm.get('floor_number')?.disable();
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to fetch room', 'error');
            }
          },
          error: (err) => {
            const msg = err.error?.message || 'A error occured while fetching room';
            this._snackbar.openSnackBar(msg, 'error');
          }
        });
    }
  }


  fetchRoomTypes() {
    this.isRoomTypeLoading = true;
    this._roomService.getRoomTypes()
      .pipe(finalize(() => this.isRoomTypeLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roomTypesList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch available rooms types', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching available rooms types';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  
  allowOnlyNumbers(event: KeyboardEvent) {
    const charCode = event.which ?? event.keyCode;
    if (charCode < 48 || charCode > 57) {
      event.preventDefault();
    }
  }

}
