import { AbstractControl, ValidatorFn } from '@angular/forms';

export const passwordMatchValidator: ValidatorFn = (control: AbstractControl) => {
  const newPassword = control.get('new_password');
  const confirmPassword = control.get('confirmed_password');

  if (!newPassword || !confirmPassword) {
    return null;
  }

  if (confirmPassword.errors && !confirmPassword.errors['passwordMismatch']) {
    return null;
  }

  if (newPassword.value !== confirmPassword.value) {
    confirmPassword.setErrors({ passwordMismatch: true });
  } else {
    confirmPassword.setErrors(null);
  }

  return null;
};

export const passwordDifferentValidator: ValidatorFn = (control: AbstractControl) => {
  const currentPassword = control.get('current_password');
  const newPassword = control.get('new_password');

  if (!currentPassword || !newPassword) {
    return null;
  }

  if (newPassword.errors && !newPassword.errors['passwordMatch']) {
    return null;
  }

  if (currentPassword.value == newPassword.value) {
    newPassword.setErrors({ passwordMatch: true });
  } else {
    newPassword.setErrors(null);
  }

  return null;
};
