import { NgModule, APP_INITIALIZER, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { HTTP_INTERCEPTORS, HttpClientModule } from '@angular/common/http';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { SharedModule } from './shared/shared.module';
import { HttpIntercept } from './core/http-interceptor';
import { InitialService } from './services/initial.service';
import { TenantService } from './services/tenant.service';
import { MAT_DATE_LOCALE } from '@angular/material/core';
import { provideMomentDateAdapter } from '@angular/material-moment-adapter';


export function initApp(initialService: InitialService) {
  return () => initialService.loadAppConfig();
}

/**
 * Resolve the host's hotel after the static config is in.
 *
 * APP_INITIALIZER factories run in the order they are registered, and this one
 * needs the `BASE_URL` that `initApp` sets, so it must stay below it. Both
 * block the first render.
 */
export function initTenant(tenantService: TenantService) {
  return () => tenantService.load();
}

//// Date Format
export const MY_DATE_FORMATS = {
  parse: {
    dateInput: 'DD/MM/YYYY', // How the user types the date
  },
  display: {
    dateInput: 'DD/MM/YYYY', // How the date is displayed in the input
    monthYearLabel: 'MMM YYYY',
    dateA11yLabel: 'LL',
    monthYearA11yLabel: 'MMMM YYYY',
  },
};


@NgModule({
  declarations: [
    AppComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    FormsModule,
    ReactiveFormsModule,
    SharedModule,
    HttpClientModule
  ],
  providers: [
    provideAnimationsAsync(),
    {
      provide: APP_INITIALIZER,
      useFactory: initApp,
      deps: [InitialService],
      multi: true
    },
    {
      /// Must stay after the initializer above: multi-providers run in
      /// registration order, and tenant-info needs the BASE_URL it sets.
      provide: APP_INITIALIZER,
      useFactory: initTenant,
      deps: [TenantService],
      multi: true
    },
    {
      provide: HTTP_INTERCEPTORS,
      useClass:HttpIntercept,
      multi:true
    },
    //// Provide the Moment adapter with your custom formats
    provideMomentDateAdapter(MY_DATE_FORMATS),
    { provide: MAT_DATE_LOCALE, useValue: 'en-GB' } // en-GB naturally uses DD/MM/YYYY
  ],
  bootstrap: [AppComponent],
  schemas: [CUSTOM_ELEMENTS_SCHEMA]
})
export class AppModule { }
