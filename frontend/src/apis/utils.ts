import axios from 'axios';
import { API_BASE } from './config';

export type TimezoneIdResponse = {
  timezoneId: string;
};

export const api = {
  getTimezoneId: async (lat: number, lng: number): Promise<TimezoneIdResponse> => {
    const { data } = await axios.post<TimezoneIdResponse>(
      `${API_BASE}/api/v1/utils/get-timezone`,
      null,
      { params: { lat, lng } },
    );
    return data;
  },
};
