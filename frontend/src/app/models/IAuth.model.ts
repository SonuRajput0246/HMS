export interface IAuthRequest {
    email?: string;
    password?: string;
}

export interface UserData {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface LoginData {
  access_token: string;
  user_data: UserData;
}

export interface LoginResponse {
  status: boolean;
  data: LoginData;
}

export interface IChangePassword {
  userEmail?: string;
  current_password?:string;
  new_password?: string;
  confirmed_password?: string;
}

export interface IResetPassword {
  userEmail?: string;
  otp?:string;
  password?: string;
  confirmed_password?: string;
}

export interface IUserProfile {
  first_name?: string;
  last_name?: string;
  email?: string;
  role_name?: string;
}

export interface ISignUp {
  first_name?: string;
  last_name?: string;
  email?: string;
  password?: string;
}