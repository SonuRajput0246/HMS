import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RoleManagementService } from '../../../services/role-management.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { ActivatedRoute, Router } from '@angular/router';
import { INavigationaBar, ISearchRequest } from '../../../models/ICommon.model';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-manage-role',
  templateUrl: './manage-role.component.html',
  styleUrl: './manage-role.component.scss'
})
export class ManageRoleComponent {

  private fb = inject(FormBuilder);
  private _roleService = inject(RoleManagementService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);

  navData: INavigationaBar[] = [];
  roleForm!: FormGroup;
  breakpoint = 3;

  isLoading = false;
  isPageLoad = false;

  roleObj: any = { id: 0 };
  isEditMode = false;

  // requestData: ISearchRequest = {
  //   page_number: 1,
  //   page_size: 10,
  //   search_value: ''
  // } as ISearchRequest;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();
    this.onResize();

    const roleId = Number(this.AR.snapshot.paramMap.get('id'));
    if (roleId) {
      this.isEditMode = true;
      this.GetRoleById(roleId);
      this.navData = [
        ...this.navData,
        { displayValue: 'Edit Role', isClickable: false, isDashboard: false }
      ];
    } else {
      this.navData = [
        ...this.navData,
        { displayValue: 'Add Role', isClickable: false, isDashboard: false }
      ];
    }
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Role Management', isClickable: true, isDashboard: false, redirectValue: '/hms/roles' }
    ]
  }

  onResize(): void {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }

  private createForm(): void {
    this.roleForm = this.fb.group({
      role_code: ['', Validators.required],
      role_name: ['', Validators.required],
      is_active: [true]
    });
  }

  private GetRoleById(roleId: number): void {
    if (roleId > 0) {
      this.isPageLoad = true;
      this._roleService.getRoleById(roleId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.isEditMode = true;
              this.roleObj = res.data;
              this.roleForm.patchValue({
                role_code: this.roleObj.role_code,
                role_name: this.roleObj.role_name,
                is_active: this.roleObj.is_active
              });
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to fetch role', 'error');
            }
          },
          error: (err) => {
            const msg = err.error?.message || 'A error occured while fetching role';
            this._snackbar.openSnackBar(msg, 'error');
          }
        });
    }
  }

  insertUpdateRole(): void {
    if (this.roleForm.invalid) {
      this.roleForm.markAllAsTouched();
      return;
    }
    const payload = {
      ...this.roleForm.value,
      id: this.roleObj?.id || 0,
      is_deleted: false
    };
    this.isLoading = true;
    this._roleService.insertUpdateRole(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Role saved successfully', "success");
            this._router.navigate(['hms/roles']);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save role', "error");
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving role';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

}
