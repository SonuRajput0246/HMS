import { IEntityResponse } from "./ICommon.model";

export interface IUserProfile {
  first_name?: string;
  last_name?: string;
  email?: string;
  role_name?: string;
  menu_access: IUserMenuAccess[];
}

export interface IUserMenuAccess extends IEntityResponse {
  module_id: number;
  module_name: string;
  menu_parent_code: number;
  display_order_no: number;
  icon: string;
  route_path: string;
  has_child_menu: boolean;
  childMenus: IUserMenuAccess[];
  module_display_name?: string;
  accessList: IAccess[];
}

export interface IAccess {
    id: number;
    is_active: boolean;
    operation_display_name: string;
    operation_name: string;
}



