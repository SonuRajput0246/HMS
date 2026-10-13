import { Component, inject } from '@angular/core';
import { RoleManagementService } from '../../../services/role-management.service';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs/operators';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { UserService } from '../../../services/user.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';

@Component({
  selector: 'app-manage-user',
  templateUrl: './manage-user.component.html',
  styleUrl: './manage-user.component.scss'
})
export class ManageUserComponent {

  private fb = inject(FormBuilder);
  private _roleService = inject(RoleManagementService);
  private _userService = inject(UserService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);

  navData: INavigationaBar[] = [];
  userForm!: FormGroup;
  breakpoint = 3;

  hidePassword = true;
  isLoading = false;
  isPageLoad = false;
  isRoleLoading = false;

  roleList: any[] = [];
  usersObj: any = { id: 0 };
  isEditMode = false;

  requestData: ISearchRequest = {
    page_number: 1,
    page_size: 10,
    search_value: ''
  } as ISearchRequest;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.onResize();
    this.fetchRoleList();

    const userId = Number(this.AR.snapshot.paramMap.get('id'));
    if (userId) {
      this.isEditMode = true;
      this.GetUserById(userId);
      this.navData = [
        ...this.navData,
        { displayValue: 'Edit User', isClickable: false, isDashboard: false }
      ];
    } else {
      this.navData = [
        ...this.navData,
        { displayValue: 'Add User', isClickable: false, isDashboard: false }
      ];
    }
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'User Management', isClickable: true, isDashboard: false, redirectValue: '/hms/users' }
    ]
  }

  onResize(): void {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }

  private createForm(): void {
    this.userForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      role_id: [{ value: null, disabled: true }, Validators.required],
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
      is_active: [true]
    });
  }

  togglePassword(): void {
    this.hidePassword = !this.hidePassword;
  }

  private fetchRoleList(): void {
    const roleControl = this.userForm.get('role_id');

    this.isRoleLoading = true;
    this.roleList = [];
    this.userForm.get('role_id')?.disable();  //// keep disabled while loading
    this._roleService.GetRoles(this.requestData)
      .pipe(finalize(() => this.isRoleLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.roleList = res.data ?? [];
            if (this.roleList.length > 0) {
              roleControl?.enable();   //// enable only when roles exists
            }
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch roles', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while fetching roles';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }
  
  insertUpdateUser(): void {
    if (this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }
    const isUpdate = !!this.usersObj?.id;
    const formValues = {
      ...this.userForm.value,
      ...this.userForm.getRawValue()
    };
    const payload = {
      ...formValues,
      id: this.usersObj?.id || 0,
      password: isUpdate ? 'XXXXXX' : formValues.password,
      is_deleted: false
    };
    this.isLoading = true;
    this._userService.insertUpdateUser(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'User saved successfully', "success");
            this._router.navigate(['hms/users']);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save user', "error");
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving user';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  GetUserById(userId: number) {
    if (userId > 0) {
      this.isPageLoad = true;

      this._userService.getUserById(userId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.isEditMode = true;
              this.usersObj = res.data;
              this.userForm.patchValue({
                id: this.usersObj.id,
                first_name: this.usersObj.first_name,
                last_name: this.usersObj.last_name,
                role_id: this.usersObj.role_id,
                email: this.usersObj.email,
                is_active: this.usersObj.is_active
              });
              this.userForm.get('email')?.disable();
              this.userForm.get('password')?.disable();
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to fetch user', 'error');
            }
          },
          error: (err) => {
            const msg = err.error?.message || 'A error occured while fetching user';
            this._snackbar.openSnackBar(msg, 'error');
          }
        });
    }
  }

}
