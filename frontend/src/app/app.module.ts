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


/**
 * Boot: load the static config, then resolve the host's hotel.
 *
 * The two steps are chained inside one initializer rather than split across
 * two. Angular invokes every APP_INITIALIZER function immediately and only
 * then awaits them together, so a second initializer would run before
 * `config.json` had set `BASE_URL` -- which `tenant-info` needs. Chaining is
 * what actually orders them; the array order alone does not.
 */
export function initApp(initialService: InitialService, tenantService: TenantService) {
  return () => initialService.loadAppConfig().then(() => tenantService.load());
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
      deps: [InitialService, TenantService],
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
