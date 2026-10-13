import { NgModule } from '@angular/core';

import { CustomSnackbarComponent } from './custom-snackbar/custom-snackbar.component';
import { MaterialModule } from './material-module';
import { NavigationBarComponent } from './navigation-bar/navigation-bar.component';
import { PageLoaderComponent } from './page-loader/page-loader.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';
import { RouterLink } from '@angular/router';
import { SnakeToTitlePipe } from '../pipes/snake-to-title.pipe';
import { NgxMatSelectSearchModule } from 'ngx-mat-select-search';

/**
 * Cross-cutting declarations every feature module imports.
 *
 * Kept deliberately small. Anything that only one feature uses belongs in that
 * feature's own module instead -- a barrel that grows without limit makes it
 * impossible to tell which module actually needs what.
 */
@NgModule({
  declarations: [
    CustomSnackbarComponent,
    NavigationBarComponent,
    PageLoaderComponent,
    PageNotFoundComponent,
    SnakeToTitlePipe
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
    NgxMatSelectSearchModule
  ],
})
export class SharedModule { }