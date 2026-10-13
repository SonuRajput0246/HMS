import { Component, Inject } from '@angular/core';
import { MAT_SNACK_BAR_DATA } from '@angular/material/snack-bar';

@Component({
  selector: 'app-custom-snackbar',
  templateUrl: './custom-snackbar.component.html',
  styleUrl: './custom-snackbar.component.scss'
})
export class CustomSnackbarComponent {

  // Material icon ligature, resolved by CustomSnackbarService from the
  // snack type. Kept as data rather than a switch here so the type -> icon
  // and type -> panelClass mappings live in one place.
  icon = '';

  message = '';

  constructor(
    @Inject(MAT_SNACK_BAR_DATA) public data: any
  ) {
    this.icon = this.data?.icon ?? '';
    this.message = this.data?.message ?? '';
  }
}