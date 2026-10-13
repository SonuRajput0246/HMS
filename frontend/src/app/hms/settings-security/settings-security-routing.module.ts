import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AuthGuard } from '../../core/auth.guard';
import { SettingsComponent } from './settings/settings.component';
import { DeactivateAccountComponent } from './security/deactivate-account/deactivate-account.component';
import { ChangePasswordComponent } from './security/change-password/change-password.component';
import { DeleteAccountComponent } from './security/delete-account/delete-account.component';
import { MfaComponent } from './security/mfa/mfa.component';

const routes: Routes = [
  {
    path: '',
    component: SettingsComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  },
  {
    path: 'security/change-password',
    component: ChangePasswordComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  },
  {
    path: 'security/setup-multi-factor-authentication',
    component: MfaComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  },
  {
    path: 'security/deactivate-account',
    component: DeactivateAccountComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  },
  {
    path: 'security/delete-account',
    component: DeleteAccountComponent,
    data: { menuId: 1 },
    canActivate: [AuthGuard]
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class SettingsSecurityRoutingModule { }
