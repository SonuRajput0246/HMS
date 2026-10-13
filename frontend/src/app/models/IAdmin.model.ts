export interface IModules {
    id?: number;
    module_name?: string;
    module_display_name?: string;
    menu_parent_code?: number;
    has_child_menu?: boolean;
    route_path?: string;
    display_order_no?: number;
    icon?: string;
    access_json?: IJson[];
    is_active?: boolean;
}

export interface IJson {
    key?: string;
    value?: boolean;
    operation_key?: string;
}

export interface IUsers {
    id?: number;
    first_name?: string;
    last_name?: string;
    role_id?: number;
    role_name?: string;
    Email?: string;
    Password?: string;
    is_active?: boolean;
    is_deleted?: boolean;
}

export interface IInventoryCategory {
    id?: number;
    name?: string;
    description?: string;
    is_active?: boolean;
    is_deleted?: boolean;
}

export interface IInventory {
    id?: number;
    name?: string;
    category_id?: number;
    category_name?: string;
    quantity?: number;
    unit?: string;
    // Purchase cost per unit, used to value stock on hand. Null means the item
    // has never been priced -- distinct from 0, which is a real zero cost.
    unit_cost?: string | number | null;
    // Default sell price for the item. Null means no price has been set.
    selling_price?: string | number | null;
    is_active?: boolean;
    is_deleted?: boolean;
}

export interface IModuleAccess {
    id?: number;
    is_active?: boolean;
    module_id?: number;
    operation_name?: string;
    operation_display_name?: string;
}

export interface IRoles {
    id?: number;
    role_name?: string;
    module_access?: IModuleAccess[];
    is_active?: boolean;
    is_deleted?: boolean;
}

//// ---------- TEMPLATES ----------
export type TemplateChannel = 'email' | 'in_app';

/// Row shape returned by POST /get-templates. The full message body is
/// deliberately absent to keep the grid payload light.
export interface ITemplate {
    id?: number;
    code?: string;
    name?: string;
    description?: string;
    channel?: TemplateChannel;
    is_active?: boolean;
    is_system?: boolean;
    version?: number;
    sort_order?: number;
    variables?: string[];
    preview_label?: string;
    has_subject?: boolean;
    has_title?: boolean;
    created_at?: string;
    updated_at?: string;
    updated_by_name?: string;
}

/// Full row returned by GET /get-template-by-id, for the edit form.
export interface ITemplateDetail extends ITemplate {
    subject_template?: string | null;
    title_template?: string | null;
    message_template?: string;
    sample_context?: { [key: string]: any };
    is_deleted?: boolean;
    deleted_at?: string | null;
    created_by?: number | null;
    updated_by?: number | null;
    created_by_name?: string | null;
    variable_audit?: ITemplateVariableAudit;
}

export interface ITemplateVariableAudit {
    declared?: string[];
    used?: string[];
    undeclared?: string[];
    unused?: string[];
}

/// Payload for POST /upsert-template. `id: 0` creates; `is_deleted: true`
/// performs the soft delete.
export interface ITemplateUpsert {
    id?: number;
    code?: string;
    name?: string;
    description?: string | null;
    channel?: TemplateChannel;
    subject_template?: string | null;
    title_template?: string | null;
    message_template?: string;
    variables?: string[];
    sample_context?: { [key: string]: any };
    is_active?: boolean;
    is_deleted?: boolean;
}

export interface ITemplateListRequest {
    page_number?: number;
    page_size?: number;
    search_value?: string;
    /// Send null, NOT '', when unfiltered. The backend validates channel with
    /// OneOf(['email','in_app']) and rejects an empty string with a 400.
    channel?: TemplateChannel | null;
    is_active?: boolean | null;
}

export interface ITemplatePreview {
    channel?: TemplateChannel;
    subject?: string;
    title?: string;
    message?: string;
    /// Full email document wrapped in the server-side layout. Populated for
    /// channel='email' only.
    html_body?: string | null;
    used_variables?: string[];
    missing_variables?: string[];
    detected_variables?: string[];
}

export interface ITemplateCodeOption {
    code?: string;
    name?: string;
}