import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { InventoryService } from '../../../services/inventory.service';
import { ActivatedRoute, Router } from '@angular/router';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { finalize } from 'rxjs/operators';
import { InstanceService } from '../../../core/config/instance.service';

@Component({
  selector: 'app-manage-category',
  templateUrl: './manage-category.component.html',
  styleUrl: './manage-category.component.scss'
})
export class ManageCategoryComponent {

  private fb = inject(FormBuilder);
  private _inventoryService = inject(InventoryService);
  private _router = inject(Router);
  private _snackbar = inject(CustomSnackbarService);
  private AR = inject(ActivatedRoute);
private _instance = inject(InstanceService);

  /** Base URL for this screen within the active product, for template use. */
  readonly invBase = `${this._instance.prefix}/inventory`;

  categoryForm!: FormGroup;
  breakpoint = 3;

  hidePassword = true;
  isLoading = false;
  isPageLoad = false;
  isRoleLoading = false;

  isEditMode = false;
  categoryObj: any = { id: 0 };

  ngOnInit(): void {
    this.createForm();
    this.onResize();

    const categoryId = Number(this.AR.snapshot.paramMap.get('id'));
    if (categoryId) {
      this.isEditMode = true;
      this.GetCategoryById(categoryId);
    }
  }

  private createForm(): void {
    this.categoryForm = this.fb.group({
      name: ['', Validators.required],
      description: ['', Validators.required],
      is_active: [true]
    });
  }

  onResize(): void {
    this.breakpoint = window.innerWidth <= 960 ? 1 : 3;
  }


  insertUpdateCategory(): void {
    if (this.categoryForm.invalid) {
      this.categoryForm.markAllAsTouched();
      return;
    }
    const payload = {
      ...this.categoryForm.value,
      id: this.categoryObj?.id || 0,
      is_deleted: false
    };
    this.isLoading = true;
    this._inventoryService.insertUpdateCategory(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Category saved successfully', "success");
            /// Back to the list within the active product. A literal 'hms' here
            /// meant a save in the cafe deployment navigated to a gated route.
            this._router.navigate([`${this._instance.prefix}/inventory/list-category`]);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save category', "error");
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'A error occured while saving category';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }


  private GetCategoryById(categoryId: number): void {
    if (categoryId > 0) {
      this.isPageLoad = true;

      this._inventoryService.getCategoryById(categoryId)
        .pipe(finalize(() => this.isPageLoad = false))
        .subscribe({
          next: (res) => {
            if (res?.status) {
              this.isEditMode = true;
              this.categoryObj = res.data;
              this.categoryForm.patchValue({
                id: this.categoryObj.id,
                name: this.categoryObj.name,
                description: this.categoryObj.description,
                is_active: this.categoryObj.is_active
              });
            } else {
              this._snackbar.openSnackBar(res?.message || 'Failed to load category', 'error');
            }
          },
          error: (err) => {
            const msg = err.error?.message || 'A error occured while fetching category';
            this._snackbar.openSnackBar(msg, 'error');
          }
        });
    }
  }

}
