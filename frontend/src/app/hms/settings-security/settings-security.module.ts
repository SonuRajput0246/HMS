import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { SettingsSecurityRoutingModule } from './settings-security-routing.module';
import { SettingsComponent } from './settings/settings.component';
import { SharedModule } from '../../shared/shared.module';
import { DeactivateAccountComponent } from './security/deactivate-account/deactivate-account.component';
import { ChangePasswordComponent } from './security/change-password/change-password.component';
import { DeleteAccountComponent } from './security/delete-account/delete-account.component';
import { MfaComponent } from './security/mfa/mfa.component';
import { QRCodeComponent  } from 'angularx-qrcode';


@NgModule({
  declarations: [
    SettingsComponent,
    DeactivateAccountComponent,
    ChangePasswordComponent,
    DeleteAccountComponent,
    MfaComponent,
  ],
  imports: [
    CommonModule,
    SettingsSecurityRoutingModule,
    SharedModule,
    QRCodeComponent 
  ]
})
export class SettingsSecurityModule { }
