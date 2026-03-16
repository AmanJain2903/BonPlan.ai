import axios from 'axios';
import { API_BASE } from './config';

export type RegisterResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type LoginResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
  token?: string;
  token_type?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
};

export type VerifyEmailResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type ChangePasswordResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type ForgotPasswordResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type ResetPasswordResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type ProfileResponse = {
  first_name?: string;
  last_name?: string;
  email?: string;
  country_code?: string;
  phone?: string;
  auth_provider?: string;
  status_code?: number;
  detail?: string;
};

export type UpdateProfileResponse = {
  message?: string;
  first_name?: string;
  last_name?: string;
  country_code?: string;
  phone?: string;
  status_code?: number;
  detail?: string;
};

export type DeleteUserResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
};

export type GoogleLoginResponse = {
  message?: string;
  status_code?: number;
  detail?: string;
  token?: string;
  token_type?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
};

export const api = {
  googleLogin: async (idToken: string): Promise<GoogleLoginResponse> => {
    const { data } = await axios.post<GoogleLoginResponse>(
      `${API_BASE}/api/v1/auth/google`,
      null,
      { params: { token: idToken } },
    );
    return data;
  },

  register: async (
    first_name: string,
    last_name: string,
    email: string,
    password: string,
    code: string | null = null,
    phone: string | null = null,
  ): Promise<RegisterResponse> => {
    const { data } = await axios.post<RegisterResponse>(
      `${API_BASE}/api/v1/auth/register`,
      null,
      { params: { first_name, last_name, email, password, code, phone } },
    );
    return data;
  },

  login: async (email: string, password: string): Promise<LoginResponse> => {
    const { data } = await axios.post<LoginResponse>(
      `${API_BASE}/api/v1/auth/login`,
      null,
      { params: { email, password } },
    );
    return data;
  },

  verifyEmail: async (token: string): Promise<VerifyEmailResponse> => {
    const { data } = await axios.post<VerifyEmailResponse>(
      `${API_BASE}/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`,
    );
    return data;
  },

  changePassword: async (token: string, current_password: string, new_password: string): Promise<ChangePasswordResponse> => {
    const { data } = await axios.post<ChangePasswordResponse>(
      `${API_BASE}/api/v1/auth/change-password`,
      null,
      { params: { token, current_password, new_password } },
    );
    return data;
  },

  forgotPassword: async (email: string): Promise<ForgotPasswordResponse> => {
    const { data } = await axios.post<ForgotPasswordResponse>(
      `${API_BASE}/api/v1/auth/forgot-password`,
      null,
      { params: { email } },
    );
    return data;
  },

  resetPassword: async (token: string, new_password: string): Promise<ResetPasswordResponse> => {
    const { data } = await axios.post<ResetPasswordResponse>(
      `${API_BASE}/api/v1/auth/reset-password`,
      null,
      { params: { token, new_password } },
    );
    return data;
  },

  getProfile: async (token: string): Promise<ProfileResponse> => {
    const { data } = await axios.get<ProfileResponse>(
      `${API_BASE}/api/v1/auth/profile`,
      { params: { token } },
    );
    return data;
  },

  updateProfile: async (
    token: string,
    first_name: string,
    last_name: string,
    country_code: string | null = null,
    phone: string | null = null,
  ): Promise<UpdateProfileResponse> => {
    const { data } = await axios.post<UpdateProfileResponse>(
      `${API_BASE}/api/v1/auth/profile`,
      null,
      { params: { token, first_name, last_name, country_code, phone } },
    );
    return data;
  },

  deleteUser: async (token: string): Promise<DeleteUserResponse> => {
    const { data } = await axios.post<DeleteUserResponse>(
      `${API_BASE}/api/v1/auth/delete`,
      null,
      { params: { token } },
    );
    return data;
  },
};
