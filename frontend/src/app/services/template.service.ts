import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse } from '../models/ICommon.model';
import {
  ITemplateCodeOption,
  ITemplateDetail,
  ITemplateListRequest,
  ITemplatePreview,
  ITemplateUpsert
} from '../models/IAdmin.model';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TemplateService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private _baseURL!: string;

  constructor() {
    this._baseURL = this.config.get('BASE_URL');
  }

  getTemplates(data: ITemplateListRequest): Observable<IEntityResponse> {
    return this.http.post(`${this._baseURL}/api/v1/template/get-templates`, data);
  }

  getTemplateById(templateId: number): Observable<IEntityResponse> {
    return this.http.get(`${this._baseURL}/api/v1/template/get-template-by-id?id=${templateId}`);
  }

  /// Distinct codes for the channel/code dropdown.
  getTemplateCodes(channel?: string): Observable<IEntityResponse> {
    const query = channel ? `?channel=${channel}` : '';
    return this.http.get(`${this._baseURL}/api/v1/template/get-template-codes${query}`);
  }

  /// Create (id=0), update, or soft delete (is_deleted=true).
  upsertTemplate(reqdata: ITemplateUpsert): Observable<IEntityResponse> {
    return this.http.post(`${this._baseURL}/api/v1/template/upsert-template`, reqdata);
  }

  /// Render an unsaved draft. Persists nothing, so it is safe to call on
  /// every keystroke in the editor's live-preview panel.
  previewTemplate(reqdata: any): Observable<IEntityResponse> {
    return this.http.post(`${this._baseURL}/api/v1/template/preview-template`, reqdata);
  }
}