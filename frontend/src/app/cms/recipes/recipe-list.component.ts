import { Component, inject, OnInit, TemplateRef, ViewChild } from '@angular/core';
import { AbstractControl, FormBuilder, FormGroup, ValidationErrors, Validators } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatTableDataSource } from '@angular/material/table';
import { ActivatedRoute } from '@angular/router';
import { finalize } from 'rxjs/operators';

import { IGenricGrid, INavigationaBar } from '../../models/ICommon.model';
import { IInventory } from '../../models/IAdmin.model';
import {
  IRecipe, IRecipeCategory, IRecipeIngredient, IStockCheck, SpiceLevel, Station, STATION_LABELS, toAmount
} from '../../models/ICms.model';
import { CmsRecipeService } from '../../services/cms/recipe.service';
import { ConfirmationService } from '../../services/confirmation.service';
import { InstanceService } from '../../core/config/instance.service';
import { InventoryService } from '../../services/inventory.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';

/**
 * One editable row in the ingredient grid.
 *
 * Not IRecipeIngredient: that is the SERVER's view of a line (it carries
 * line_cost and in_stock, which are outputs). This is the CLIENT's view -- a
 * draft, where `id` may be 0 for a row the operator just added and quantity is
 * still whatever they typed. Mixing the two would invite someone to bind
 * line_cost into the form and then be surprised that the server ignores it.
 */
interface IIngredientRow {
  id: number;
  inventory_id: number | null;
  inventory_name: string | null;
  quantity: string;
  unit: string;
  is_optional: boolean;
  is_prepped: boolean;
  /** Echoed back after a save, so the operator can see the effect of a change. */
  line_cost?: string;
  in_stock?: boolean;
}

/**
 * Menu & recipe management.
 *
 * The recipes tab is the admin view of the menu, the categories tab is the
 * reference data behind it. They live together because a recipe is worthless
 * without a category to sit in on the POS menu.
 *
 * Three things this screen deliberately does NOT let the operator do by hand,
 * each because the server owns that value:
 *  - set cost_price (derived from the ingredient lines),
 *  - set a station outside the seeded enum,
 *  - sell an 86'd dish (is_available is a switch, not a field).
 */
@Component({
  selector: 'app-recipe-list',
  templateUrl: './recipe-list.component.html',
  styleUrl: './recipe-list.component.scss'
})
export class RecipeListComponent implements OnInit {

  //// Inject Services
  private _recipeService = inject(CmsRecipeService);
  private _inventoryService = inject(InventoryService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _dialog = inject(MatDialog);
  private _route = inject(ActivatedRoute);
  private _instance = inject(InstanceService);
  private _fb = inject(FormBuilder);

  @ViewChild('recipeFormTpl') recipeFormTpl!: TemplateRef<unknown>;
  @ViewChild('categoryFormTpl') categoryFormTpl!: TemplateRef<unknown>;

  //// Constants
  readonly stationLabels = STATION_LABELS;
  readonly spiceLevels: SpiceLevel[] = ['none', 'mild', 'medium', 'hot', 'extra_hot'];

  /**
   * Mirrors INGREDIENT_UNITS in recipe_ingredient_schema.py.
   *
   * Deliberately wider than the inventory unit allow-list (pcs/kg/gm/ltr/ml):
   * a recipe line is often a PORTION of a bulk stock unit -- "60 ml of oil per
   * burger" has to be expressible even though no inventory row is stored in ml
   * on its own. 'mg' is here for the same reason (spices).
   */
  readonly ingredientUnits: string[] = ['pcs', 'kg', 'gm', 'mg', 'ltr', 'ml'];

  //// State Properties
  navData: INavigationaBar[] = [];
  selectedTabIndex = 0;

  isPageLoad = false;
  isCategoryLoad = false;
  isSaving = false;

  // ---- recipes tab ----
  gridSearch = '';
  filterCategoryId: number | null = null;
  filterStation: string | null = null;
  /// Tri-state so "Available" and "86'd" are both selectable filters; a
  /// boolean-only control could never express "show me everything".
  filterAvailability: boolean | null = null;

  recipeList: IRecipe[] = [];
  recipeDataSource = new MatTableDataSource<IRecipe>();
  displayedColumns: string[] = ['sr', 'display_name', 'category_display_name', 'selling_price', 'cost_price', 'margin_percent', 'station', 'total_time_minutes', 'is_available', 'actions'];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 };

  categoryList: IRecipeCategory[] = [];
  stationList: string[] = [];

  /// ids with an in-flight availability flip, so a fast double toggle cannot
  /// send two updateAvailability calls and leave the row showing the older value.
  busyIds = new Set<number>();

  // ---- dialog state ----
  editingRecipe: IRecipe | null = null;
  editingCategory: IRecipeCategory | null = null;

  recipeForm!: FormGroup;
  categoryForm!: FormGroup;

  /// Ingredient grid state, only meaningful while the recipe dialog is open.
  ingredientRows: IIngredientRow[] = [];
  isIngredientSave = false;
  stockCheck: IStockCheck | null = null;
  isStockLoad = false;

  /// The server's own numbers after the last ingredient save. Showing our own
  /// arithmetic next to a server-derived cost would guarantee the two drift the
  /// first time a quantity has more than two decimal places.
  liveCostPrice: string | null = null;
  liveMarginPercent: string | null = null;

  inventoryList: IInventory[] = [];
  isInventoryLoad = false;

  //// Request State
  private requestData = {
    page_number: 1,
    page_size: 10,
    search_value: '',
    category_id: null as number | null,
    station: null as string | null,
    is_available: null as boolean | null
  };

  private categoryRequest = { page_number: 1, page_size: 200, search_value: '' };

  ngOnInit(): void {
    this.buildForms();
    this.initNavigation();
    this.loadCategories();
    this.loadStations();
    this.fetchRecipes();
  }

  //// ------------------------------------------------------------------
  ////  Navigation
  //// ------------------------------------------------------------------

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: this._instance.homeUrl },
      { displayValue: 'CMS', isClickable: false, isDashboard: false },
      {
        displayValue: this._route.snapshot.data['breadcrumb'] || 'Menu & Recipes',
        isClickable: false,
        isDashboard: false
      }
    ];
  }

  //// ------------------------------------------------------------------
  ////  Forms
  //// ------------------------------------------------------------------

  private buildForms(): void {
    this.recipeForm = this._fb.group({
      name: ['', [Validators.required, Validators.maxLength(100)]],
      display_name: ['', [Validators.required, Validators.maxLength(100)]],
      category_id: [null],
      description: ['', Validators.maxLength(1000)],
      instructions: ['', Validators.maxLength(2000)],
      selling_price: [null as number | null, [Validators.required, Validators.min(0)]],
      station: ['other', Validators.required],
      prep_time_minutes: [0, [Validators.min(0), Validators.max(1440)]],
      cook_time_minutes: [0, [Validators.min(0), Validators.max(1440)]],
      is_vegetarian: [false],
      is_vegan: [false],
      is_spicy: [false],
      default_spice_level: [null],
      is_recommended: [false],
      is_available: [true],
      display_order: [0, [Validators.min(0)]],
      is_active: [true]
    }, { validators: [this.veganImpliesVegetarian()] });

    /**
     * Turning Vegan on ticks Vegetarian too. The schema guard rejects
     * vegan-without-vegetarian, and an operator who ticks only Vegan has not
     * made a mistake they can see -- so the form resolves the impossible pair
     * instead of letting them save into a 422 and read "error" with no clue.
     */
    this.recipeForm.get('is_vegan')?.valueChanges.subscribe((vegan: boolean) => {
      if (vegan) {
        const veg = this.recipeForm.get('is_vegetarian');
        if (veg && !veg.value) {
          veg.setValue(true);
          veg.markAsDirty();
        }
      }
    });

    this.categoryForm = this._fb.group({
      name: ['', [Validators.required, Validators.maxLength(50)]],
      display_name: ['', [Validators.required, Validators.maxLength(50)]],
      description: ['', Validators.maxLength(1000)],
      display_order: [0, [Validators.min(0)]],
      is_active: [true]
    });
  }

  /**
   * Schema guard, mirrored client-side.
   *
   * Vegan is a strict subset of vegetarian, so "vegan but not vegetarian" is
   * a state that cannot exist on a menu -- the customer would see a dish
   * badged vegan that the POS also calls non-vegetarian. The server rejects
   * the pair with a message on `is_vegetarian`; running the same rule here
   * means the error is attached to the control the operator has to fix instead
   * of arriving as a bare 400.
   */
  private veganImpliesVegetarian(): (group: AbstractControl) => ValidationErrors | null {
    return (group: AbstractControl): ValidationErrors | null => {
      const vegan = group.get('is_vegan')?.value;
      const vegetarian = group.get('is_vegetarian')?.value;
      return vegan && !vegetarian ? { veganRequiresVegetarian: true } : null;
    };
  }

  //// ------------------------------------------------------------------
  ////  Reads
  //// ------------------------------------------------------------------

  private fetchRecipes(): void {
    this.isPageLoad = true;
    this.requestData.search_value = this.gridSearch;

    this._recipeService.getRecipes(this.requestData)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch recipes', 'error');
            return;
          }
          this.recipeList = res.data || [];
          this.pageDet.total_docs = res.meta?.total_records || 0;
          this.pageDet.limit = this.requestData.page_size;
          this.recipeDataSource.data = this.recipeList;
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while fetching recipes', 'error'
        )
      });
  }

  private loadCategories(): void {
    this._recipeService.getCategories(this.categoryRequest)
      .pipe(finalize(() => this.isCategoryLoad = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch recipe categories', 'error');
            return;
          }
          this.categoryList = res.data || [];
          this.categoryDataSource.data = this.categoryList;
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while fetching recipe categories', 'error'
        )
      });
  }

  /**
   * Stations come from the seeded enum table, not from a hardcoded list here.
   * The schema cannot validate station itself (marshmallow is static), so the
   * enum table is the single source of truth -- a literal list in this
   * component would be a second copy that drifts the day an admin adds a
   * station. STATION_LABELS only supplies the display words.
   */
  private loadStations(): void {
    this._recipeService.getStations()
      .subscribe({
        next: (res) => {
          this.stationList = res?.status && Array.isArray(res.data) ? res.data : [];
        },
        error: () => {
          // 503 means the enum seeder has not been run. Fall back to the
          // compiled-in list so the form is still usable and the operator can
          // see which value they are saving; the server will reject anything
          // genuinely invalid.
          this.stationList = Object.keys(STATION_LABELS);
        }
      });
  }

  /// Inventory options for the ingredient grid. Fetched lazily on first open
  /// of the editor because the recipes tab itself never needs them.
  private ensureInventoryLoaded(): void {
    if (this.inventoryList.length || this.isInventoryLoad) return;

    this.isInventoryLoad = true;
    this._inventoryService.getInventories({ page_number: 1, page_size: 500 })
      .pipe(finalize(() => this.isInventoryLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.inventoryList = res.data || [];
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch inventory items', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while fetching inventory items', 'error'
        )
      });
  }

  //// ------------------------------------------------------------------
  ////  UI Event Handlers — recipes tab
  //// ------------------------------------------------------------------

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchRecipes();
  }

  /**
   * Same three-character threshold as the inventory lists, for the same reason:
   * the backend search is a LIKE on name / recipe_code, so one character returns
   * most of the menu and the pager stops meaning anything.
   */
  applyFilter(): void {
    if (this.gridSearch.length >= 3 || this.gridSearch.length === 0) {
      this.requestData.page_number = 1;
      this.fetchRecipes();
    }
  }

  onCategoryFilter(): void {
    this.requestData.category_id = this.filterCategoryId;
    this.requestData.page_number = 1;
    this.fetchRecipes();
  }

  onStationFilter(): void {
    this.requestData.station = this.filterStation;
    this.requestData.page_number = 1;
    this.fetchRecipes();
  }

  onAvailabilityFilter(): void {
    this.requestData.is_available = this.filterAvailability;
    this.requestData.page_number = 1;
    this.fetchRecipes();
  }

  clearFilter(): void {
    this.gridSearch = '';
    this.filterCategoryId = null;
    this.filterStation = null;
    this.filterAvailability = null;
    this.requestData.search_value = '';
    this.requestData.category_id = null;
    this.requestData.station = null;
    this.requestData.is_available = null;
    this.requestData.page_number = 1;
    this.fetchRecipes();
  }

  //// ------------------------------------------------------------------
  ////  86 / un-86
  //// ------------------------------------------------------------------

  /**
   * The one-tap availability switch.
   *
   * Deliberately NOT a slide-toggle bound straight to is_available: that would
   * flip the model before the server agrees, so a failed call would leave a
   * dish showing as sellable when the POS has already refused it. The row only
   * changes once updateAvailability comes back true.
   *
   * The row also dims and gains an "86'd" chip while is_available is false --
   * the whole point of an 86 is that the cashier cannot ring it up by accident,
   * and a cashier scanning a long menu reads the row, not a switch's position.
   */
  onToggleAvailability(recipe: IRecipe, isAvailable: boolean): void {
    if (!recipe.id || this.busyIds.has(recipe.id)) return;

    this.busyIds.add(recipe.id);
    this._recipeService.updateAvailability(recipe.id, isAvailable)
      .pipe(finalize(() => this.busyIds.delete(recipe.id!)))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            recipe.is_available = isAvailable;
            this._snackbar.openSnackBar(
              res.message || (isAvailable ? 'Recipe is back on the menu' : 'Recipe 86\'d'), 'success'
            );
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to change availability', 'error');
            // Re-read the row so the switch cannot keep showing a value the
            // server never accepted.
            this.fetchRecipes();
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err?.error?.message || 'An error occurred while changing availability', 'error'
          );
          this.fetchRecipes();
        }
      });
  }

  //// ------------------------------------------------------------------
  ////  Recipe dialog
  //// ------------------------------------------------------------------

  onAddRecipe(): void {
    this.editingRecipe = null;
    this.recipeForm.reset({
      name: '',
      display_name: '',
      category_id: null,
      description: '',
      instructions: '',
      selling_price: null,
      station: this.defaultStation,
      prep_time_minutes: 0,
      cook_time_minutes: 0,
      is_vegetarian: false,
      is_vegan: false,
      is_spicy: false,
      default_spice_level: null,
      is_recommended: false,
      is_available: true,
      display_order: this.recipeList.length,
      is_active: true
    });
    this.resetIngredientState();
    this.ensureInventoryLoaded();
    this._dialog.open(this.recipeFormTpl, {
      width: '900px',
      maxWidth: '96vw',
      autoFocus: false,
      panelClass: 'rcp-dialog-panel'
    });
  }

  onEditRecipe(recipe: IRecipe): void {
    (document.activeElement as HTMLElement)?.blur();
    this.editingRecipe = recipe;

    /**
     * Open against the single-recipe fetch, not the row. The list endpoint
     * omits `instructions` (it is a long blob nobody scans) and the
     * ingredient lines entirely -- patching the form from the row would load
     * an empty method sheet that then saves as an empty one.
     */
    this.isSaving = true;
    this._recipeService.getRecipeById(recipe.id!)
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to load the recipe', 'error');
            return;
          }

          const full: IRecipe = res.data;
          this.recipeForm.reset({
            name: full.name || '',
            display_name: full.display_name || '',
            category_id: full.category_id ?? null,
            description: full.description || '',
            instructions: full.instructions || '',
            selling_price: Number(full.selling_price || 0),
            station: full.station || 'other',
            prep_time_minutes: full.prep_time_minutes ?? 0,
            cook_time_minutes: full.cook_time_minutes ?? 0,
            is_vegetarian: !!full.is_vegetarian,
            is_vegan: !!full.is_vegan,
            is_spicy: !!full.is_spicy,
            default_spice_level: full.default_spice_level ?? null,
            is_recommended: !!full.is_recommended,
            is_available: full.is_available ?? true,
            display_order: full.display_order ?? 0,
            is_active: full.is_active ?? true
          });

          this.resetIngredientState();
          this.ingredientRows = (full.ingredients || []).map((ing: IRecipeIngredient) => ({
            id: ing.id || 0,
            inventory_id: ing.inventory_id ?? null,
            inventory_name: ing.inventory_name ?? null,
            quantity: ing.quantity ?? '0',
            unit: ing.unit || 'pcs',
            is_optional: !!ing.is_optional,
            is_prepped: !!ing.is_prepped,
            line_cost: ing.line_cost,
            in_stock: ing.in_stock
          }));
          this.liveCostPrice = full.cost_price ?? null;
          this.liveMarginPercent = full.margin_percent ?? null;

          this.ensureInventoryLoaded();
          this._dialog.open(this.recipeFormTpl, {
            width: '900px',
            maxWidth: '96vw',
            autoFocus: false,
            panelClass: 'rcp-dialog-panel'
          });

          this.checkStock();
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while loading the recipe', 'error'
        )
      });
  }

  private resetIngredientState(): void {
    this.ingredientRows = [];
    this.stockCheck = null;
    this.liveCostPrice = null;
    this.liveMarginPercent = null;
    this.isStockLoad = false;
  }

  saveRecipe(dialogRef: { close: () => void }): void {
    if (this.recipeForm.invalid) {
      this.recipeForm.markAllAsTouched();
      this._snackbar.openSnackBar('Please correct the highlighted fields', 'warn');
      return;
    }

    this.isSaving = true;
    const value = this.recipeForm.value;

    /**
     * cost_price is NOT in this payload, on purpose. The server derives it from
     * the ingredient lines on every ingredient write and does not accept it
     * from a client -- sending one would let the header margin and the
     * ingredient editor disagree, which is exactly the contradiction the
     * schema docstring exists to prevent. The figure shown in this dialog
     * therefore always comes from the server.
     */
    const payload = {
      id: this.editingRecipe?.id || 0,
      name: value.name,
      display_name: value.display_name,
      category_id: value.category_id || null,
      description: value.description || null,
      instructions: value.instructions || null,
      selling_price: value.selling_price,
      station: value.station,
      prep_time_minutes: value.prep_time_minutes || 0,
      cook_time_minutes: value.cook_time_minutes || 0,
      is_vegetarian: !!value.is_vegetarian,
      is_vegan: !!value.is_vegan,
      is_spicy: !!value.is_spicy,
      default_spice_level: value.default_spice_level || null,
      is_recommended: !!value.is_recommended,
      is_available: !!value.is_available,
      display_order: value.display_order || 0,
      is_active: !!value.is_active,
      is_deleted: false
    };

    this._recipeService.upsertRecipe(payload)
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to save the recipe', 'error');
            return;
          }

          this._snackbar.openSnackBar(res.message || 'Recipe saved successfully', 'success');

          /**
           * A newly created recipe has no id in the dialog's state yet, so the
           * ingredient grid would have nowhere to save to -- replaceIngredients
           * takes the recipe id in the URL. Adopting the saved row keeps the
           * dialog open and lets the operator add ingredients straight away,
           * instead of making them save, close, reopen.
           */
          const saved: IRecipe = res.data;
          if (saved?.id) {
            this.editingRecipe = saved;
          }

          this.fetchRecipes();
          this.loadCategories();
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while saving the recipe', 'error'
        )
      });
  }

  onDeleteRecipe(recipe: IRecipe): void {
    (document.activeElement as HTMLElement)?.blur();

    this._confirmService
      .confirm(
        'Delete this recipe?',
        `${recipe.display_name || recipe.name} will be removed from the menu and 86'd immediately. ` +
        'Historical orders keep their own copy of the name and price.',
        'Yes, Delete it!'
      )
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDeleteRecipe(recipe);
        }
      });
  }

  private executeDeleteRecipe(recipe: IRecipe): void {
    if (!recipe.id) return;

    this.isPageLoad = true;

    /**
     * Soft delete through the same upsert -- there is no DELETE endpoint.
     * is_available goes false alongside is_active so a deleted dish stops
     * being sellable in the same call rather than lingering on the POS menu
     * until someone notices.
     */
    this._recipeService.upsertRecipe({
      id: recipe.id,
      name: recipe.name,
      display_name: recipe.display_name || recipe.name,
      category_id: recipe.category_id ?? null,
      description: recipe.description || null,
      selling_price: recipe.selling_price,
      station: recipe.station,
      prep_time_minutes: recipe.prep_time_minutes ?? 0,
      cook_time_minutes: recipe.cook_time_minutes ?? 0,
      is_vegetarian: !!recipe.is_vegetarian,
      is_vegan: !!recipe.is_vegan,
      is_spicy: !!recipe.is_spicy,
      is_recommended: !!recipe.is_recommended,
      is_available: false,
      display_order: recipe.display_order ?? 0,
      is_active: false,
      is_deleted: true
    })
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Recipe deleted successfully', 'success');
            this.fetchRecipes();
            this.loadCategories();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete the recipe', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while deleting the recipe', 'error'
        )
      });
  }

  //// ------------------------------------------------------------------
  ////  Ingredient grid
  //// ------------------------------------------------------------------

  addIngredientRow(): void {
    // Default the unit to whatever the chosen inventory item is stocked in:
    // a line saying "2 pcs of 1 kg flour" is a unit error waiting to happen.
    this.ingredientRows = [...this.ingredientRows, {
      id: 0,
      inventory_id: null,
      inventory_name: null,
      quantity: '1',
      unit: 'pcs',
      is_optional: false,
      is_prepped: false
    }];
  }

  removeIngredientRow(index: number): void {
    this.ingredientRows = this.ingredientRows.filter((_, i) => i !== index);
  }

  /** Keeps the unit in step with the inventory row, and caches the name so the
   *  grid cell still reads sensibly before the select's own text settles. */
  onInventoryPicked(row: IIngredientRow, inventoryId: number | null): void {
    const item = this.inventoryList.find(i => i.id === inventoryId);
    row.inventory_id = inventoryId;
    row.inventory_name = item?.name ?? null;
    if (item?.unit) {
      row.unit = item.unit;
    }
  }

  

  /**
   * Save the whole grid in one call.
   *
   * replaceIngredients matches rows to existing lines by inventory_id, so a new
   * row's id is 0 and any inventory_id missing from the payload is removed
   * server-side. That makes the grid a pure function of what is on screen --
   * there is no "which rows did I add?" bookkeeping for the client to get
   * wrong, which is why this is one call and not a series of upserts plus
   * deletes.
   */
  saveIngredients(): void {
    const recipeId = this.editingRecipe?.id;
    if (!recipeId) {
      this._snackbar.openSnackBar('Save the recipe first, then add its ingredients', 'warn');
      return;
    }

    if (this.ingredientRows.length === 0) {
      // Legal but almost certainly a mistake: a recipe with no lines costs 0 and
      // the margin column silently reads 100%.
      this._snackbar.openSnackBar('This recipe has no ingredient lines yet', 'warn');
      return;
    }

    const invalidRow = this.ingredientRows.findIndex(r => !r.inventory_id || !Number(r.quantity) || !r.unit);
    if (invalidRow > -1) {
      this._snackbar.openSnackBar(`Row ${invalidRow + 1} needs an item, a quantity and a unit`, 'warn');
      return;
    }

    // The schema enforces one row per inventory item; catching it here points at
    // the row instead of surfacing a nested field_name the operator cannot see.
    const seen = new Set<number>();
    const dupIndex = this.ingredientRows.findIndex(r => {
      const id = r.inventory_id as number;
      if (seen.has(id)) return true;
      seen.add(id);
      return false;
    });
    if (dupIndex > -1) {
      this._snackbar.openSnackBar(`Row ${dupIndex + 1} repeats an item already in the list`, 'warn');
      return;
    }

    this.isIngredientSave = true;
    const payload = this.ingredientRows.map(r => ({
      id: r.id || 0,
      inventory_id: r.inventory_id,
      quantity: r.quantity,
      unit: r.unit,
      is_optional: !!r.is_optional,
      is_prepped: !!r.is_prepped
    }));

    this._recipeService.replaceIngredients(recipeId, payload)
      .pipe(finalize(() => this.isIngredientSave = false))
      .subscribe({
        next: (res) => {
          if (!res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Failed to save ingredients', 'error');
            return;
          }

          this._snackbar.openSnackBar(res.message || 'Ingredients saved', 'success');

          /**
           * Adopt the server's rows rather than keeping the local drafts: the
           * server assigned ids to the new lines, restated cost_price, and may
           * have normalised a quantity. Keeping our version would show stale
           * line costs and make a second save send id 0 for a row that now has
           * one.
           */
          this.ingredientRows = (res.data?.ingredients || []).map((ing: IRecipeIngredient) => ({
            id: ing.id || 0,
            inventory_id: ing.inventory_id ?? null,
            inventory_name: ing.inventory_name ?? null,
            quantity: ing.quantity ?? '0',
            unit: ing.unit || 'pcs',
            is_optional: !!ing.is_optional,
            is_prepped: !!ing.is_prepped,
            line_cost: ing.line_cost,
            in_stock: ing.in_stock
          }));
          this.liveCostPrice = res.data?.cost_price ?? null;
          this.liveMarginPercent = res.data?.margin_percent ?? null;

          this.checkStock();
          this.fetchRecipes();
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while saving ingredients', 'error'
        )
      });
  }

  /**
   * "Can we make this right now, and how many portions?"
   *
   * The question a manager actually asks about a dish, and one the recipe row
   * cannot answer: the recipe only knows its ingredients, not what is on the
   * shelf. Optional lines are skipped by the server, so a missing garnish does
   * not read as unsellable.
   */
  checkStock(): void {
    const recipeId = this.editingRecipe?.id;
    if (!recipeId) return;

    this.isStockLoad = true;
    this._recipeService.checkStock(recipeId)
      .pipe(finalize(() => this.isStockLoad = false))
      .subscribe({
        next: (res) => {
          this.stockCheck = res?.status ? res.data : null;
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'Could not check ingredient stock', 'error'
        )
      });
  }

  //// ------------------------------------------------------------------
  ////  Categories tab
  //// ------------------------------------------------------------------

  categoryDataSource = new MatTableDataSource<IRecipeCategory>();
  categoryColumns: string[] = ['sr', 'name', 'display_name', 'description', 'display_order', 'recipe_count', 'is_active', 'actions'];

  onAddCategory(): void {
    this.editingCategory = null;
    this.categoryForm.reset({
      name: '',
      display_name: '',
      description: '',
      display_order: this.categoryList.length,
      is_active: true
    });
    this._dialog.open(this.categoryFormTpl, {
      width: '560px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'rcp-dialog-panel'
    });
  }

  onEditCategory(category: IRecipeCategory): void {
    (document.activeElement as HTMLElement)?.blur();
    this.editingCategory = category;
    this.categoryForm.reset({
      name: category.name || '',
      display_name: category.display_name || '',
      description: category.description || '',
      display_order: category.display_order ?? 0,
      is_active: category.is_active ?? true
    });
    this._dialog.open(this.categoryFormTpl, {
      width: '560px',
      maxWidth: '95vw',
      autoFocus: false,
      panelClass: 'rcp-dialog-panel'
    });
  }

  saveCategory(dialogRef: { close: () => void }): void {
    if (this.categoryForm.invalid) {
      this.categoryForm.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    const value = this.categoryForm.value;

    this._recipeService.upsertCategory({
      id: this.editingCategory?.id || 0,
      name: value.name,
      display_name: value.display_name,
      description: value.description || null,
      display_order: value.display_order || 0,
      is_active: !!value.is_active,
      is_deleted: false
    })
      .pipe(finalize(() => this.isSaving = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Category saved successfully', 'success');
            dialogRef.close();
            // Reloads the recipes tab's category filter at the same time --
            // a new category is useless to the operator if the filter cannot
            // see it.
            this.loadCategories();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save the category', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while saving the category', 'error'
        )
      });
  }

  onDeleteCategory(category: IRecipeCategory): void {
    (document.activeElement as HTMLElement)?.blur();

    /**
     * The backend does NOT cascade: the recipe -> category_id FK is
     * ON DELETE SET NULL, so deleting a category leaves its recipes alive and
     * they fall into "Uncategorised" on the POS menu. Recoverable, but only if
     * the operator is told the number before they click.
     */
    const count = category.recipe_count ?? 0;
    const warning = count > 0
      ? `${count} recipe${count === 1 ? '' : 's'} will move to "Uncategorised" on the POS menu. The recipes are not deleted.`
      : 'This category has no recipes.';

    this._confirmService
      .confirm('Delete this category?', warning, 'Yes, Delete it!')
      .then((result) => {
        if (result.isConfirmed) {
          this.executeDeleteCategory(category);
        }
      });
  }

  private executeDeleteCategory(category: IRecipeCategory): void {
    if (!category.id) return;

    this.isCategoryLoad = true;
    this._recipeService.upsertCategory({
      id: category.id,
      name: category.name,
      display_name: category.display_name || category.name,
      description: category.description || null,
      display_order: category.display_order ?? 0,
      is_active: false,
      is_deleted: true
    })
      .pipe(finalize(() => this.isCategoryLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res.message || 'Category deleted successfully', 'success');
            this.loadCategories();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to delete the category', 'error');
          }
        },
        error: (err) => this._snackbar.openSnackBar(
          err?.error?.message || 'An error occurred while deleting the category', 'error'
        )
      });
  }

  //// ------------------------------------------------------------------
  ////  Template helpers
  //// ------------------------------------------------------------------

  /**
   * 'other' is the server's load_default for station, and the only sensible
   * choice for a dish nobody has routed yet. Pre-selecting it beats leaving the
   * field empty, because an empty select would be rejected by the schema's
   * allow_none=False and the operator would not know why.
   */
  get defaultStation(): string {
    return this.stationList.includes('other') ? 'other' : (this.stationList[0] || 'other');
  }

  /**
   * Colour the margin by band rather than printing a bare number.
   *
   * A dish selling below or barely above cost is the thing a manager needs to
   * catch on this screen, and a percentage sitting in the same neutral grey as
   * a healthy one does not get caught.
   */
  marginClass(recipe: IRecipe): string {
    const pct = toAmount(recipe.margin_percent);
    if (pct < 0) return 'm-loss';
    if (pct < 30) return 'm-thin';
    if (pct < 50) return 'm-ok';
    return 'm-good';
  }

  /**
   * Label for a station, with a fallback for values the enum table knows but
   * STATION_LABELS does not. An admin can add a station at runtime; the screen
   * must then show the raw key rather than "undefined".
   */
  stationLabel(station?: Station | string | null): string {
    if (!station) return 'Other';
    const known = this.stationLabels[station as Station];
    if (known) return known;
    return station.charAt(0).toUpperCase() + station.slice(1);
  }

  /** Class fragment so station pills share the CMS status palette. */
  stationClass(station?: Station | string | null): string {
    return station ? `stn-${station}` : 'stn-other';
  }

  categoryLabel(recipe: IRecipe): string {
    return recipe.category_display_name || recipe.category_name || 'Uncategorised';
  }

  isBusy(id?: number): boolean {
    return !!id && this.busyIds.has(id);
  }

  getSrNo(index: number): number {
    return (this.requestData.page_size * (this.requestData.page_number - 1)) + (index + 1);
  }

  get currentPageIndex(): number {
    return this.requestData.page_number - 1;
  }

  /** Schema guard surfaced inline so the operator is told WHICH flag to fix. */
  get veganNeedsVegetarian(): boolean {
    return !!this.recipeForm?.errors?.['veganRequiresVegetarian'];
  }
}