import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { CustomSnackbarComponent } from './custom-snackbar.component';

export type SnackbarType = 'success' | 'error' | 'warn' | 'info';

/**
 * Single source of truth for the type -> presentation mapping.
 *
 * `panelClass` is attached by Material to the snack-bar *container*; the
 * surface tint, accent bar and icon colours in src/styles.scss are keyed off
 * it, so a type added here also needs a matching entry in the $snack-states
 * map in that file.
 */
const SNACKBAR_STYLES: Record<SnackbarType, { panelClass: string; icon: string }> = {
  success: { panelClass: 'success-snackbar', icon: 'check_circle' },
  error: { panelClass: 'error-snackbar', icon: 'error' },
  warn: { panelClass: 'warn-snackbar', icon: 'warning' },
  info: { panelClass: 'info-snackbar', icon: 'info' }
};

@Injectable({
  providedIn: 'root'
})
export class CustomSnackbarService {

  constructor(
    private _snackBar: MatSnackBar
  ) { }

  openSnackBar(message: string, action: string) {
    // Unknown types fall back to the neutral 'info' look instead of dropping
    // the message on the floor.
    const type = (action in SNACKBAR_STYLES ? action : 'info') as SnackbarType;
    const style = SNACKBAR_STYLES[type];

    this._snackBar.openFromComponent(CustomSnackbarComponent, {
      data: {
        message: message,
        snackType: type,
        icon: style.icon,
        snackBar: this._snackBar
      },
      horizontalPosition: 'center',
      verticalPosition: 'top',
      duration: 2500,
      panelClass: [style.panelClass]
    });
  }
}