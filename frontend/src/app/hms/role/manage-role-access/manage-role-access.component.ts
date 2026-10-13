import { Component, inject } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { IModuleAccess, IModules, IRoles } from '../../../models/IAdmin.model';
import { ActivatedRoute, Router } from '@angular/router';
import { RoleManagementService } from '../../../services/role-management.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { MatTableDataSource } from '@angular/material/table';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-manage-role-access',
  templateUrl: './manage-role-access.component.html',
  styleUrl: './manage-role-access.component.scss'
})
export class ManageRoleAccessComponent {

  private _roleService = inject(RoleManagementService);
  private _snackbar = inject(CustomSnackbarService);
  private AR = inject(ActivatedRoute)
  private _router = inject(Router);

  navData: INavigationaBar[] = [];
  roleObj: IRoles = {
    is_active: true
  } as IRoles;

  rolesAccessList?: IModules[] = [];
  roleId: number = 0
  isLoading?: boolean;
  isPageLoad?: boolean;

  displayedColumns: string[] = ["menuname", "events"]
  dataSource = new MatTableDataSource<IModules>();

  ngOnInit(): void {
    this.initNavigation();
    this.roleId = Number(this.AR.snapshot.paramMap.get('id'));
    
    if (this.roleId) {
      this.GetRoleById(this.roleId);
      this.navData = [
        ...this.navData,
        { displayValue: 'Role Module Access', isClickable: false, isDashboard: false }
      ];
    }
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Role Management', isClickable: true, isDashboard: false }
    ];
  }


  private GetRoleById(roleId: number): void {
    if (roleId > 0) {
      this.isPageLoad = true;
      this._roleService.getRoleById(roleId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.roleObj = res.data;
              this.GetAllRolesAccess();
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

  GetAllRolesAccess() {
    this.isPageLoad = true;
    this.rolesAccessList = [];
    this._roleService.getRoleModuleAccessList()
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.rolesAccessList = res.data;

            this.rolesAccessList!.forEach((module) => {
              module.is_active = false;
              module.access_json!.forEach((access) => {
                access.value = false;
              });
            });

            if (this.roleObj.id! > 0) {
              this.rolesAccessList!.forEach((module) => {
                module.is_active = false;

                let checkForEditMode = this.roleObj.module_access?.filter(x => x.module_id == module.id);
                if (checkForEditMode != null && checkForEditMode.length > 0) {
                  module.access_json!.forEach((access) => {
                    access.value = false;

                    let checkAccess = checkForEditMode?.filter(z => z.operation_name == access.operation_key && z.is_active == true);
                    if (checkAccess != null && checkAccess.length > 0) {
                      access.value = true;

                      let isModuleAccess = checkForEditMode?.filter(y => y.operation_name == 'View' && y.is_active == true);
                      if (isModuleAccess && isModuleAccess != null && isModuleAccess.length > 0) {
                        module.is_active = true;
                      }
                    }
                    
                  });
                }
              });
            }
            this.dataSource = new MatTableDataSource<IModules>(this.rolesAccessList);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch role access', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while fetching role access';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })
  }




  // Add this method to handle checkbox changes in the UI
  onModuleToggle(module: IModules): void {
    // 1. If we disable a parent, disable all its children
    if (!module.is_active) {
      this.rolesAccessList?.forEach(child => {
        if (child.menu_parent_code === module.id) {
          child.is_active = false;
          // Also uncheck all operations within the child
          child.access_json?.forEach(access => access.value = false);
          // Recursive call if there are deeper levels
          this.onModuleToggle(child); 
        }
      });
      
      // Also uncheck operations for the current module being toggled
      module.access_json?.forEach(access => access.value = false);
    } else {
      // 2. If we enable a child, we MUST ensure the parent is enabled
      if (module.menu_parent_code !== 0) {
        const parent = this.rolesAccessList?.find(m => m.id === module.menu_parent_code);
        if (parent && !parent.is_active) {
          parent.is_active = true;
        }
      }
    }
  }

  // Helper to check if a parent is disabled (used for the [disabled] attribute in HTML)
  isParentDisabled(module: IModules): boolean {
    if (module.menu_parent_code === 0) return false;
    const parent = this.rolesAccessList?.find(m => m.id === module.menu_parent_code);
    // If parent doesn't exist or is inactive, this child should be disabled
    return parent ? !parent.is_active : false;
  }



  updateRoleAccessList() {
    const newModuleAccess: IModuleAccess[] = [];
    let counter = 1;
    this.dataSource.data.forEach((element: IModules) => {
      if (element.is_active) {
        newModuleAccess.push({
          id: counter++,
          is_active: true,
          module_id: element.id,
          operation_name: 'View',
          operation_display_name: 'View'
        });

        element.access_json?.forEach((access) => {
          if (access.value) {
            newModuleAccess.push({
              id: counter++,
              is_active: true,
              module_id: element.id,
              operation_name: access.operation_key,
              operation_display_name: access.key
            });
          }
        });
      }
    });  
    this._roleService.updateRoleAccess(this.roleId, newModuleAccess)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._router.navigate(['hms/roles']);
            this._snackbar.openSnackBar(res?.message || 'Role access updated successfully', 'success');
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to update role access', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while updating role access';
          this._snackbar.openSnackBar(msg, 'error');
        }
      })

  }




}
