export interface User {
  id: number;
  username: string;
  email: string;
  points: number;
  daily_usage_count: number;
  mcp_daily_usage_count: number;
  daily_limit: number;
  mcp_daily_limit: number;
  is_unlimited: boolean;
  can_use_mcp: boolean;
  is_admin: boolean;
  created_at: string;
  last_reset_at: string;
  mcp_last_reset_at: string;
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
  stock_id: number;
  user_id: number;
  symbol: string;
  added_at: string;
  notes?: string;
  stock: {
    symbol: string;
    name: string;
    exchange: string;
    currency: string;
  };
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

export interface McpStatus {
  can_use_mcp: boolean;
  mcp_usage_available: boolean;
  points: number;
  mcp_daily_usage_count: number;
  mcp_daily_limit: number;
}

export interface McpTokenInfo {
  id: number;
  name: string;
  token_prefix: string;
  is_active: boolean;
  last_used_at?: string | null;
  last_used_ip?: string | null;
  expires_at?: string | null;
  created_at: string;
  revoked_at?: string | null;
  user_id?: number | null;
  username?: string | null;
}

export interface McpTokenCreatePayload {
  token: string;
  token_info: McpTokenInfo;
}

export interface ExternalMcpToolInfo {
  full_name: string;
  llm_name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface ExternalMcpServerInfo {
  id: string;
  base_url: string;
  enabled: boolean;
  timeout_seconds?: number | null;
  header_names: string[];
  tool_count: number;
  tools: ExternalMcpToolInfo[];
}
