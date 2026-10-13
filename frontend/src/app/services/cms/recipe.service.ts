import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfig } from '../../core/config/config';
import { IEntityResponse } from '../../models/ICommon.model';
import { IRecipe, IRecipeCategory, IStockCheck } from '../../models/ICms.model';

/**
 * Menu management: recipes, their categories, and the ingredient lines that
 * drive cost_price and the stock checks.
 */
@Injectable({ providedIn: 'root' })
export class CmsRecipeService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private readonly baseURL: string;

  constructor() {
    this.baseURL = this.config.get('BASE_URL');
  }

  // ---- categories -----------------------------------------------------

  getCategories(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe-category/get`, data);
  }

  upsertCategory(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe-category/upsert`, data);
  }

  /** Recipe count, so the UI can warn before orphaning a category's menu. */
  getCategoryRecipeCount(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/recipe-category/get-recipe-count?id=${id}`);
  }

  // ---- recipes --------------------------------------------------------

  getRecipes(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe/get`, data);
  }

  getRecipeById(id: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/recipe/get-by-id?id=${id}`);
  }

  /** Whole menu grouped by category. What the POS item picker renders. */
  getMenu(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe/get-menu`, data);
  }

  getStations(): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/recipe/get-stations`);
  }

  /**
   * Create or update a recipe.
   *
   * cost_price is deliberately NOT part of the payload -- the server derives it
   * from the ingredient lines, so sending it would let the two disagree.
   */
  upsertRecipe(data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe/upsert`, data);
  }

  /** 86 / un-86 a dish without opening the full editor. */
  updateAvailability(id: number, isAvailable: boolean, reason?: string): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe/update-availability`, {
      id, is_available: isAvailable, reason: reason ?? null
    });
  }

  // ---- ingredients ----------------------------------------------------

  getIngredients(recipeId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/recipe-ingredient/${recipeId}`);
  }

  upsertIngredient(recipeId: number, data: any): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe-ingredient/${recipeId}/upsert`, data);
  }

  /**
   * Save the whole ingredient grid in one call.
   *
   * Lines are matched by inventory_id server-side, so ids may be omitted or
   * left as 0 for rows that are new. Any inventory_id absent from the list is
   * removed. This is the natural shape for an editable table -- sending deltas
   * would make the client reconcile which rows were added vs dropped.
   */
  replaceIngredients(recipeId: number, ingredients: any[]): Observable<IEntityResponse> {
    return this.http.post(`${this.baseURL}/api/v1/recipe-ingredient/${recipeId}/replace`, {
      recipe_id: recipeId, ingredients
    });
  }

  deleteIngredient(recipeId: number, ingredientId: number): Observable<IEntityResponse> {
    return this.http.post(
      `${this.baseURL}/api/v1/recipe-ingredient/${recipeId}/delete/${ingredientId}`, {});
  }

  /** Can this dish be made right now, and how many portions? */
  checkStock(recipeId: number): Observable<IEntityResponse> {
    return this.http.get(`${this.baseURL}/api/v1/recipe-ingredient/${recipeId}/check-stock`);
  }
}