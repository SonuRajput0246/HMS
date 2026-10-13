import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { AppConfig } from '../core/config/config';
import { IEntityResponse, IGenericPagination } from '../models/ICommon.model';
import { Observable } from 'rxjs';
import { IModuleAccess, IRoles } from '../models/IAdmin.model';
@Injectable({
  providedIn: 'root'
})
export class RoleManagementService {

  private http = inject(HttpClient);
  private config = inject(AppConfig);

  private _baseURL!: string;

  constructor() {
    this._baseURL = this.config.get('BASE_URL');
  }

  
  GetRoles(data: IGenericPagination): Observable<IEntityResponse>{
    return this.http.post(`${this._baseURL}/api/v1/admin/get-roles`, data);
  }

  insertUpdateRole(reqdata: IRoles): Observable<IEntityResponse> {
    return this.http.post(`${this._baseURL}/api/v1/admin/upsert-role`, reqdata)
  }

  getRoleById(roleId: number): Observable<IEntityResponse> {
    return this.http.get(`${this._baseURL}/api/v1/admin/get-role-by-id?id=${roleId}`)
  }

  getRoleModuleAccessList(): Observable<IEntityResponse> {
    return this.http.get(`${this._baseURL}/api/v1/admin/get-modules`)
  }

  updateRoleAccess(roleId: number, newModuleAccess: IModuleAccess[]): Observable<IEntityResponse> {
    const body = {
      role_id: roleId,
      role_module_access: newModuleAccess
    }
    return this.http.post(`${this._baseURL}/api/v1/admin/update-role-access`, body)
  }


}
