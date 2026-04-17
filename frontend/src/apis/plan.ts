import axios from 'axios';
import { API_BASE, AGENT_BASE } from './config';

export type RegisterResponse = {
    message?: string;
    status_code?: number;
    trip_id?: string;
};

export type RBACResponse = {
    message?: string;
    status_code?: number;
    rbac?: string;
};

export interface Plan {
    id: string;
    planning_type: string;
    routing_style: string;
    origin: string;
    destinations: any[];
    start_date: string;
    end_date: string;
    pace: string;
    budget: string;
    adults: number;
    children: number;
    status: string;
    role: string;
    created_at: string;
    updated_at: string;
}

export interface GetPlansResponse {
    message?: string;
    status_code?: number;
    plans?: Plan[];
}

export interface TripItinerary {
    id: string;
    title: string | null;
    origin: string | null;
    destinations: string[];
    start_date: any;
    end_date: any;
    cost: number | null;
    days: number | null;
    events: any[];
    tips: string[];
    status: string;
    created_at: string;
    updated_at: string;
}

export interface GetPlanResponse {
    message?: string;
    status_code?: number;
    plan?: Plan;
    tripItinerary?: TripItinerary;
}

export interface UpdatePlanResponse {
    message?: string;
    status_code?: number;
    plan?: Plan;
}

export interface DeletePlanResponse {
    message?: string;
    status_code?: number;
}

export const api = {
    draftPlan: async (token: string, bodyData: any): Promise<RegisterResponse> => {
        const { data } = await axios.post<RegisterResponse>(
            `${API_BASE}/api/v1/plan/draft-plan`,
            bodyData,
            { params: { token } },
        );
        return data;
    },
    getRBAC: async (token: string, id: string): Promise<RBACResponse> => {
        const { data } = await axios.get<RBACResponse>(
            `${API_BASE}/api/v1/plan/rbac/${id}`,
            { params: { token } },
        );
        return data;
    },
    getPlans: async (token: string): Promise<GetPlansResponse> => {
        const { data } = await axios.get<GetPlansResponse>(
            `${API_BASE}/api/v1/plan/plans`,
            { params: { token } },
        );
        return data;
    },
    getPlan: async (token: string, id: string): Promise<GetPlanResponse> => {
        const { data } = await axios.get<GetPlanResponse>(
            `${API_BASE}/api/v1/plan/${id}`,
            { params: { token } },
        );
        return data;
    },
    deletePlan: async (token: string, id: string): Promise<DeletePlanResponse> => {
        const { data } = await axios.delete<DeletePlanResponse>(
            `${API_BASE}/api/v1/plan/${id}`,
            { params: { token } },
        );
        return data;
    },
    generateSoloPlan: async (token: string, id: string, bodyData: any, signal?: AbortSignal): Promise<Response> => {
        return await fetch(`${AGENT_BASE}/agent/api/v1/solo-planner/generate/solo/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(bodyData),
            signal
        });
    },
};
