import axios from 'axios';
import { API_BASE } from './config';

export type RegisterResponse = {
    message?: string;
    status_code?: number;
    detail?: string;
};

export const api = {
    draftPlan: async (token: string, bodyData: any): Promise<RegisterResponse> => {
        const { data } = await axios.post<RegisterResponse>(
            `${API_BASE}/api/v1/plan-draft/draft-plan`,
            bodyData,
            { params: { token } },
        );
        return data;
    },
};
