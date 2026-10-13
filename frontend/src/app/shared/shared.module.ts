import { NgModule } from '@angular/core';

// import { AccordionAnchorDirective, AccordionLinkDirective, AccordionDirective } from './accordion';
// import { MenuItems } from './menu-items';
import { CustomSnackbarComponent } from './custom-snackbar/custom-snackbar.component';
import { MaterialModule } from './material-module';
import { NavigationBarComponent } from './navigation-bar/navigation-bar.component';
import { PageLoaderComponent } from './page-loader/page-loader.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';
import { RouterLink } from '@angular/router';
import { SnakeToTitlePipe } from '../pipes/snake-to-title.pipe';
import { CurrencyInrPipe } from '../pipes/currency-inr.pipe';
import { NgxMatSelectSearchModule } from 'ngx-mat-select-search';

@NgModule({
  declarations: [
    CustomSnackbarComponent,
    NavigationBarComponent,
    PageLoaderComponent,
    PageNotFoundComponent,
    SnakeToTitlePipe,
    CurrencyInrPipe
  ],
  imports: [
    CommonModule,
    MaterialModule,
    FormsModule,
    ReactiveFormsModule,
    RouterLink,
    NgxMatSelectSearchModule
    
  ],
  exports: [
    CommonModule,
    CustomSnackbarComponent,
    MaterialModule,
    NavigationBarComponent,
    PageLoaderComponent,
    FormsModule,
    ReactiveFormsModule,
    SnakeToTitlePipe,
    CurrencyInrPipe,
    NgxMatSelectSearchModule
   ],
  providers: []
})
export class SharedModule { }
