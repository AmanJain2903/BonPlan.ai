import axios from 'axios';
import { API_BASE } from './config';

export type RegisterResponse = {
    message?: string;
    status_code?: number;
    detail?: string;
};

export interface DraftPlan {
    id: string;
    planning_type: string;
    routing_style: string;
    origin: string;
    destinations: any[];
    start_date: string;
    end_date: string;
    pace: string;
    budget: string;
    conversational_context: string;
    adults: number;
    children: number;
    created_at: string;
    updated_at: string;
}

export interface GetDraftPlansResponse {
    message?: string;
    status_code?: number;
    draft_plans?: DraftPlan[];
    detail?: string;
}

export const api = {
    draftPlan: async (token: string, bodyData: any): Promise<RegisterResponse> => {
        const { data } = await axios.post<RegisterResponse>(
            `${API_BASE}/api/v1/plan-draft/draft-plan`,
            bodyData,
            { params: { token } },
        );
        return data;
    },
    getDraftPlans: async (token: string): Promise<GetDraftPlansResponse> => {
        const { data } = await axios.get<GetDraftPlansResponse>(
            `${API_BASE}/api/v1/plan-draft/draft-plans`,
            { params: { token } },
        );
        return data;
    },
};
