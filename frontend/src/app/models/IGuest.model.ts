export interface IGuest {
    id?: number;
    first_name?: string;
    last_name?: string;
    gender?: string;
    date_of_birth?: string;
    email?: string;
    phone?: string;
    address?: string;
    city?: string;
    country?: string;
    id_type?: string;
    id_number?: string;
    nationality?: string;
    vip_status?: boolean;
    blacklist_status?: boolean;
    notes?: string;
    is_active?: boolean;
    is_deleted?: boolean;
}
