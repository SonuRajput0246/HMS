export interface IEntityResponse {
    status?: boolean;
    message?: string;
    errorCode?: string;
    extraBoolValue?: boolean;
    success?: any;
    extraValue?: string;
    data?: any;
    meta?: any;
}

export interface INavigationaBar {
    displayValue?: string;
    isClickable?: boolean;
    redirectValue?: string;
    isDashboard?: boolean;
}

export interface IGenericPagination {
    page_size?: number;
    page_number?: number;
}

export interface ISearchRequest extends IGenericPagination {
    search_value?: string;
}

export interface IGenricGrid {
    total_docs: number;
    limit: number;
}

export interface LoginSlide {
  id: number;
  title: string;
  image_path: string;
  alt_text: string;
  display_order: number;
}

export interface IEnumOption {
  option_key: string;
  option_label: string;
  /**
   * Material icon name, e.g. 'mail'. Only populated for enums that define one
   * (template_channel). Null for the rest, so always supply a fallback before
   * binding this to <mat-icon> -- a null renders an empty box.
   */
  icon?: string | null;
  sort_order: number;
  is_default: boolean;
}