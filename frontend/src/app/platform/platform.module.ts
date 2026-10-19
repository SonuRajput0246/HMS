import { CUSTOM_ELEMENTS_SCHEMA, NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule } from '@angular/material/dialog';

import { SharedModule } from '../shared/shared.module';
import { PlatformRoutingModule } from './platform-routing.module';
import { PlatformLoginComponent } from './login/login.component';
import { PlatformLayoutComponent } from './layout/layout.component';
import { PlatformDashboardComponent } from './dashboard/dashboard.component';
import { PlatformActivityComponent } from './activity/activity.component';
import { AdminListComponent } from './admins/list/list.component';
import { ManageAdminComponent } from './admins/manage-admin/manage-admin.component';
import { ResetPasswordDialogComponent } from './admins/reset-password-dialog/reset-password-dialog.component';
import { PlatformSecurityComponent } from './security/security.component';
import { TenantListComponent } from './tenants/list/list.component';
import { ManageTenantComponent } from './tenants/manage-tenant/manage-tenant.component';
import { ResetHotelAdminPasswordDialogComponent } from './tenants/reset-admin-password-dialog/reset-admin-password-dialog.component';
import { QRCodeComponent } from 'angularx-qrcode';

/**
 * The platform console. SharedModule already re-exports CommonModule,
 * MaterialModule and the reactive forms modules, which is where every widget
 * on these screens comes from.
 *
 * `MatDialogModule` is NOT part of SharedModule, and both dialogs on the
 * management screens need it. Imported here rather than in the two lists, so
 * adding a third dialog does not mean remembering a third import.
 *
 * `QRCodeComponent` is standalone and needed only by the sign-in and security
 * screens' MFA enrolment, which render the otpauth URI as a scannable code.
 *
 * Lazy-loaded behind a `canMatch` host guard in `app-routing.module.ts`, so
 * none of this is downloaded on a hotel host.
 */
@NgModule({
  declarations: [
    PlatformLoginComponent,
    PlatformLayoutComponent,
    PlatformDashboardComponent,
    PlatformActivityComponent,
    AdminListComponent,
    ManageAdminComponent,
    ResetPasswordDialogComponent,
    PlatformSecurityComponent,
    TenantListComponent,
    ManageTenantComponent,
    ResetHotelAdminPasswordDialogComponent,
  ],
  imports: [
    CommonModule,
    PlatformRoutingModule,
    SharedModule,
    ReactiveFormsModule,
    MatDialogModule,
    QRCodeComponent,
  ],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
})
export class PlatformModule {}
