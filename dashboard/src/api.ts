import axios from 'react';
import axiosInstance from 'axios';

const API_BASE = 'http://localhost:8000'; // Assuming this is backend port

export const api = axiosInstance.create({
  baseURL: `${API_BASE}/api/v1/rate-limiting-admin`,
});

export const fetchConfigs = async () => {
  const { data } = await api.get('/configs');
  return data.configs;
};

export const fetchUsage = async (scope?: string, periodBucket?: string) => {
  const params: Record<string, any> = {};
  if (scope) params.scope = scope;
  if (periodBucket) params.period_bucket = periodBucket;
  const { data } = await api.get('/usage', { params });
  return data.usage;
};

export const createConfig = async (config: any) => {
  const { data } = await api.post('/create-rate-limit-config', config);
  return data;
};

export const updateConfig = async (config: any) => {
  const { data } = await api.put('/update-rate-limit-config', config);
  return data;
};

export const deleteConfig = async (params: { sku?: string, sku_id?: string }) => {
  const { data } = await api.delete('/delete-rate-limit-config', { data: params });
  return data;
};
