import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

// Custom Validator for Minimum Age
export function minAgeValidator(minAge: number): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    if (!control.value) {
      return null; // Let 'required' validator handle empty values
    }

    const dob = new Date(control.value);
    const today = new Date();

    let age = today.getFullYear() - dob.getFullYear();
    const monthDiff = today.getMonth() - dob.getMonth();

    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
      age--;
    }

    return age >= minAge ? null : { underAge: true };
  };
}