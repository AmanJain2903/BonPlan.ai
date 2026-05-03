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
    origin: any;
    destinations: any[];
    start_date: any;
    end_date: any;
    pace: string;
    budget: string;
    adults: number;
    children: number;
    status: string;
    role: string;
    owner?: UserSummary;
    created_at: string;
    updated_at: string;
}

export type ShareAccessRole = 'shared_viewer' | 'shared_editor';

export interface UserSummary {
    first_name: string;
    last_name: string;
    email: string;
}

export interface TripMemberAccess extends UserSummary {
    id: string;
    user_id?: string | null;
    role: string;
    invitation_status: 'pending' | 'accepted';
    accepted: boolean;
    is_owner: boolean;
    created_at?: string;
    updated_at?: string;
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

export interface TripMembersResponse {
    message?: string;
    status_code?: number;
    current_user_role?: string;
    owner?: UserSummary;
    members?: TripMemberAccess[];
}

export interface ShareTripResponse {
    message?: string;
    status_code?: number;
    member?: TripMemberAccess;
}

export interface CreateShareLinkResponse {
    message?: string;
    status_code?: number;
    url?: string;
    role?: string;
}

export interface AcceptTripInvitationResponse {
    message?: string;
    status_code?: number;
    trip_id?: string;
    planning_type?: string;
    role?: string;
}

function filenameFromContentDisposition(disposition?: string): string | null {
    if (!disposition) return null;
    const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].replace(/"/g, ''));
    const match = disposition.match(/filename="?([^";]+)"?/i);
    return match?.[1] || null;
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
    getTripMembers: async (token: string, id: string): Promise<TripMembersResponse> => {
        const { data } = await axios.get<TripMembersResponse>(
            `${API_BASE}/api/v1/plan/${id}/members`,
            { params: { token } },
        );
        return data;
    },
    shareTrip: async (
        token: string,
        id: string,
        bodyData: { email: string; role: ShareAccessRole },
    ): Promise<ShareTripResponse> => {
        const { data } = await axios.post<ShareTripResponse>(
            `${API_BASE}/api/v1/plan/${id}/share`,
            bodyData,
            { params: { token } },
        );
        return data;
    },
    createShareLink: async (
        token: string,
        id: string,
        bodyData: { role: ShareAccessRole },
    ): Promise<CreateShareLinkResponse> => {
        const { data } = await axios.post<CreateShareLinkResponse>(
            `${API_BASE}/api/v1/plan/${id}/share-link`,
            bodyData,
            { params: { token } },
        );
        return data;
    },
    acceptTripInvitation: async (
        authToken: string,
        invitationToken: string,
    ): Promise<AcceptTripInvitationResponse> => {
        const { data } = await axios.post<AcceptTripInvitationResponse>(
            `${API_BASE}/api/v1/plan/invitations/accept`,
            null,
            { params: { auth_token: authToken, invitation_token: invitationToken } },
        );
        return data;
    },
    removeTripMember: async (token: string, id: string, memberId: string): Promise<DeletePlanResponse> => {
        const { data } = await axios.delete<DeletePlanResponse>(
            `${API_BASE}/api/v1/plan/${id}/members/${memberId}`,
            { params: { token } },
        );
        return data;
    },
    requestEditAccess: async (token: string, id: string): Promise<DeletePlanResponse> => {
        const { data } = await axios.post<DeletePlanResponse>(
            `${API_BASE}/api/v1/plan/${id}/access-requests/edit`,
            null,
            { params: { token } },
        );
        return data;
    },
    downloadTripItineraryPdf: async (
        token: string,
        id: string,
    ): Promise<{ blob: Blob; filename: string }> => {
        const response = await axios.get<Blob>(
            `${API_BASE}/api/v1/plan/${id}/download`,
            { params: { token }, responseType: 'blob' },
        );
        return {
            blob: response.data,
            filename: filenameFromContentDisposition(response.headers['content-disposition']) || `bonplan-itinerary-${id}.pdf`,
        };
    },
    elevateTripAccess: async (
        authToken: string,
        invitationToken: string,
    ): Promise<AcceptTripInvitationResponse> => {
        const { data } = await axios.post<AcceptTripInvitationResponse>(
            `${API_BASE}/api/v1/plan/invitations/elevate`,
            null,
            { params: { auth_token: authToken, invitation_token: invitationToken } },
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
    chatWithItinerary: async (token: string, id: string, bodyData: any, signal?: AbortSignal): Promise<Response> => {
        return await fetch(`${AGENT_BASE}/agent/api/v1/chat/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(bodyData),
            signal
        });
    },
    respondToQuestion: async (
        token: string,
        id: string,
        body: { call_id: string; answer: string | null; skipped: boolean },
    ): Promise<Response> => {
        return await fetch(`${AGENT_BASE}/agent/api/v1/solo-planner/generate/solo/${id}/respond`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(body),
        });
    },
};
