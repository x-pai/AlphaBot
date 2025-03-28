export interface User {
  id: number;
  username: string;
  email: string;
  points: number;
  daily_usage_count: number;
  daily_limit: number;
  is_unlimited: boolean;
  is_admin: boolean;
  created_at: string;
  last_reset_at: string;
}

export interface LoginForm {
  username: string;
  password: string;
}

export interface RegisterForm {
  username: string;
  email: string;
  password: string;
  invite_code: string;
}

export interface SavedStock {
  id: number;
  user_id: number;
  symbol: string;
  name: string;
  created_at: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
} 