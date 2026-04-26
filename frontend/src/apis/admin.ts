import axios from 'axios';
import { API_BASE } from './config';


export const api = {
  fetchConfigs: async (token: string) => {
    const { data } = await axios.get<{ configs: any[] }>(`${API_BASE}/api/v1/rate-limiting-admin/configs`, { params: { token } });
    return data.configs;
  },
  fetchUsage: async (token: string, scope?: string, periodBucket?: string) => {
    const params: Record<string, any> = { token };
    if (scope) params.scope = scope;
    if (periodBucket) params.period_bucket = periodBucket;
    const { data } = await axios.get<{ usage: any[] }>(`${API_BASE}/api/v1/rate-limiting-admin/usage`, { params });
    return data.usage;
  },
  createConfig: async (token: string, config: any) => {
    const { data } = await axios.post<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/create-rate-limit-config`, config, { params: { token } });
    return data;
  },
  updateConfig: async (token: string, config: any) => {
    const { data } = await axios.put<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/update-rate-limit-config`, config, { params: { token } });
    return data;
  },
  deleteConfig: async (token: string, params: { sku?: string, sku_id?: string }) => {
    const { data } = await axios.delete<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/delete-rate-limit-config`, { params: { ...params, token } });
    return data;
  },
};
