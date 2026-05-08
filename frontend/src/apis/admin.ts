import axios from 'axios';
import { API_BASE } from './config';

export type SupportTicket = {
  id: string;
  user_id: string | null;
  user_email: string;
  subject: string;
  body: string;
  status: 'OPEN' | 'RESOLVED';
  acknowledged: boolean;
  created_at: string;
  updated_at: string;
};

export type FAQ = {
  id: string;
  question: string;
  answer: string;
  order: number;
  is_published: boolean;
  created_at: string;
  updated_at: string;
};

export type RateLimitAlertSettings = {
  enabled: boolean;
  thresholds: number[];
  updated_at?: string | null;
};

export type RateLimitConfig = {
  id?: string;
  sku?: string;
  sku_id?: string;
  service?: string;
  description?: string;
  provider?: string;
  limit?: number;
  period?: string;
  scope?: string;
  reset_minute?: number;
  reset_hour?: number;
  reset_day?: number;
  reset_month?: number;
};

export type RateLimitUsageRecord = {
  id: string;
  sku: string;
  user_id: string;
  user_name: string;
  period_bucket: string;
  usage: number;
  limit: number;
  scope: string;
  period: string;
  updated_at?: string | null;
};

export type AdminAnalyticsFilters = {
  days?: number;
  planning_type?: string;
  status?: string;
  auth_provider?: string;
  search?: string;
};

export type AdminAnalyticsOverview = {
  filters: {
    days: number;
    planning_type: string;
    status: string;
    auth_provider: string;
    search: string;
    start: string | null;
    end: string | null;
  };
  summary: Record<string, number>;
  collaboration: Record<string, number>;
  operations: Record<string, number>;
  breakdowns: {
    statuses: Record<string, number>;
    planning_types: Record<string, number>;
    auth_providers: Record<string, number>;
    budgets: Record<string, number>;
    paces: Record<string, number>;
    top_destinations: { name: string; count: number }[];
    top_rate_limit_skus: { sku: string; usage: number }[];
  };
  series: { date: string; users: number; drafts: number; trips: number; generated: number }[];
  recent_itineraries: {
    id: string;
    trip_id: string;
    title: string | null;
    origin: string | null;
    destinations: string[];
    days: number | null;
    cost: number | null;
    status: string;
    updated_at: string | null;
  }[];
};

export const api = {
  fetchAnalyticsOverview: async (token: string, filters: AdminAnalyticsFilters = {}) => {
    const params: Record<string, string | number> = { token };
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params[key] = value;
    });
    const { data } = await axios.get<AdminAnalyticsOverview & { status_code: number }>(`${API_BASE}/api/v1/admin-analytics/overview`, { params });
    return data;
  },
  fetchConfigs: async (token: string) => {
    const { data } = await axios.get<{ configs: RateLimitConfig[] }>(`${API_BASE}/api/v1/rate-limiting-admin/configs`, { params: { token } });
    return data.configs;
  },
  fetchUsage: async (token: string, scope?: string, periodBucket?: string) => {
    const params: Record<string, string> = { token };
    if (scope) params.scope = scope;
    if (periodBucket) params.period_bucket = periodBucket;
    const { data } = await axios.get<{ usage: RateLimitUsageRecord[] }>(`${API_BASE}/api/v1/rate-limiting-admin/usage`, { params });
    return data.usage;
  },
  createConfig: async (token: string, config: RateLimitConfig) => {
    const { data } = await axios.post<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/create-rate-limit-config`, config, { params: { token } });
    return data;
  },
  updateConfig: async (token: string, config: RateLimitConfig) => {
    const { data } = await axios.put<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/update-rate-limit-config`, config, { params: { token } });
    return data;
  },
  deleteConfig: async (token: string, params: { sku?: string, sku_id?: string }) => {
    const { data } = await axios.delete<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/delete-rate-limit-config`, { params: { ...params, token } });
    return data;
  },
  getAlertSettings: async (token: string) => {
    const { data } = await axios.get<{ settings: RateLimitAlertSettings }>(`${API_BASE}/api/v1/rate-limiting-admin/alert-settings`, { params: { token } });
    return data.settings;
  },
  updateAlertSettings: async (token: string, settings: RateLimitAlertSettings) => {
    const { data } = await axios.put<{ settings: RateLimitAlertSettings }>(`${API_BASE}/api/v1/rate-limiting-admin/alert-settings`, settings, { params: { token } });
    return data.settings;
  },

  // Support
  submitTicket: async (token: string, subject: string, body: string) => {
    const { data } = await axios.post<{ message: string; ticket_id: string }>(`${API_BASE}/api/v1/support/ticket`, { token, subject, body });
    return data;
  },
  getPublicFaqs: async () => {
    const { data } = await axios.get<{ faqs: Omit<FAQ, 'is_published' | 'created_at' | 'updated_at'>[] }>(`${API_BASE}/api/v1/support/faqs`);
    return data.faqs;
  },
  adminGetFaqs: async (token: string) => {
    const { data } = await axios.get<{ faqs: FAQ[] }>(`${API_BASE}/api/v1/support/admin/faqs`, { params: { token } });
    return data.faqs;
  },
  adminCreateFaq: async (token: string, faq: { question: string; answer: string; order: number; is_published: boolean }) => {
    const { data } = await axios.post<{ message: string; id: string }>(`${API_BASE}/api/v1/support/admin/faqs`, { token, ...faq });
    return data;
  },
  adminUpdateFaq: async (token: string, faqId: string, updates: Partial<Omit<FAQ, 'id' | 'created_at' | 'updated_at'>>) => {
    const { data } = await axios.put<{ message: string }>(`${API_BASE}/api/v1/support/admin/faqs/${faqId}`, { token, ...updates });
    return data;
  },
  adminDeleteFaq: async (token: string, faqId: string) => {
    const { data } = await axios.delete<{ message: string }>(`${API_BASE}/api/v1/support/admin/faqs/${faqId}`, { params: { token } });
    return data;
  },
  adminGetTickets: async (token: string, status?: string) => {
    const params: Record<string, string> = { token };
    if (status) params.status = status;
    const { data } = await axios.get<{ tickets: SupportTicket[] }>(`${API_BASE}/api/v1/support/admin/tickets`, { params });
    return data.tickets;
  },
  adminUpdateTicketStatus: async (token: string, ticketId: string, status: 'OPEN' | 'RESOLVED') => {
    const { data } = await axios.put<{ message: string }>(`${API_BASE}/api/v1/support/admin/tickets/${ticketId}/status`, { token, status });
    return data;
  },
  adminAcknowledgeTicket: async (token: string, ticketId: string) => {
    const { data } = await axios.post<{ message: string }>(`${API_BASE}/api/v1/support/admin/tickets/${ticketId}/acknowledge`, null, { params: { token } });
    return data;
  },
  adminReplyToTicket: async (token: string, ticketId: string, message: string) => {
    const { data } = await axios.post<{ message: string }>(`${API_BASE}/api/v1/support/admin/tickets/${ticketId}/reply`, { token, message });
    return data;
  },
};
