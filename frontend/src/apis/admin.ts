import axios from 'axios';
import { API_BASE } from './config';


export const api = {
  fetchConfigs: async () => {
    const { data } = await axios.get<{ configs: any[] }>(`${API_BASE}/api/v1/rate-limiting-admin/configs`);
    return data.configs;
  },
  fetchUsage: async (scope?: string, periodBucket?: string) => {
    const params: Record<string, any> = {};
    if (scope) params.scope = scope;
    if (periodBucket) params.period_bucket = periodBucket;
    const { data } = await axios.get<{ usage: any[] }>(`${API_BASE}/api/v1/rate-limiting-admin/usage`, { params });
    return data.usage;
  },
  createConfig: async (config: any) => {
    const { data } = await axios.post<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/create-rate-limit-config`, config);
    return data;
  },
  updateConfig: async (config: any) => {
    const { data } = await axios.put<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/update-rate-limit-config`, config);
    return data;
  },
  deleteConfig: async (params: { sku?: string, sku_id?: string }) => {
    const { data } = await axios.delete<{ message: string, status_code: number }>(`${API_BASE}/api/v1/rate-limiting-admin/delete-rate-limit-config`, { params });
    return data;
  },
};
