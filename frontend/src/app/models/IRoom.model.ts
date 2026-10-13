import { ISearchRequest } from "./ICommon.model";

export interface IFilterRooms extends ISearchRequest {
    room_type_id?: number;
    room_status?: string;
}

export interface IRooms {
    id?: number;
    room_number?: string;
    room_type_id?: number;
    floor_number?: string;
    room_status?: string;
    view?: number;
    notes?: string;
    is_active?: boolean;
}