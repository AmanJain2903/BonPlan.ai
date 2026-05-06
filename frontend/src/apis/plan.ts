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
    cost?: number | null;
    itinerary_title?: string | null;
    has_events?: boolean;
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

export type AnchorEventType = 'FLIGHT' | 'HOTEL' | 'CAR_RENTAL' | 'ACTIVITY' | 'DINING' | 'OTHER';

export interface SmartAnchorUserInputs {
    // FLIGHT
    flight_number?: string;
    airline?: string;
    departure_date?: string;
    departure_time?: string;           // HH:MM
    arrival_time?: string;             // HH:MM
    departure_airport?: string;        // display label (UI only)
    departure_airport_place_id?: string;
    departure_airport_lat?: number;
    departure_airport_lng?: number;
    arrival_airport?: string;          // display label (UI only)
    arrival_airport_place_id?: string;
    arrival_airport_lat?: number;
    arrival_airport_lng?: number;
    // HOTEL
    hotel_name?: string;
    checkin_date?: string;
    checkout_date?: string;
    checkin_time?: string;             // HH:MM
    checkout_time?: string;            // HH:MM
    // CAR_RENTAL
    company?: string;
    car_model?: string;
    pickup_date?: string;
    dropoff_date?: string;
    pickup_location?: string;          // display label (UI only)
    pickup_location_place_id?: string;
    pickup_location_lat?: number;
    pickup_location_lng?: number;
    dropoff_location?: string;         // display label (UI only)
    dropoff_location_place_id?: string;
    dropoff_location_lat?: number;
    dropoff_location_lng?: number;
    pickup_time?: string;    // HH:MM
    dropoff_time?: string;   // HH:MM
    // ACTIVITY / DINING / OTHER
    name?: string;
    date?: string;
    start_time?: string;     // HH:MM
    end_time?: string;       // HH:MM
    // Common
    location?: string;               // display label (UI only)
    location_place_id?: string;
    location_lat?: number;
    location_lng?: number;
    notes?: string;
    cost?: number;           // USD
    booking_url?: string;
}

export interface SmartAnchor {
    id: string;
    type: AnchorEventType;
    user_inputs: SmartAnchorUserInputs;
    details: Record<string, any> | null;
    prefill_status: 'none';
    start_time?: string;       // HH:MM — when this anchor starts (ACTIVITY/DINING/OTHER)
    end_time?: string;         // HH:MM — when this anchor ends (ACTIVITY/DINING/OTHER)
    duration_minutes?: number; // for ACTIVITY / DINING / OTHER only
}

export interface SmartAnchorsResponse {
    message?: string;
    status_code?: number;
    smart_anchors?: SmartAnchor[];
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
    smart_anchors: SmartAnchor[];
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
    updateSmartAnchors: async (token: string, id: string, smart_anchors: SmartAnchor[]): Promise<SmartAnchorsResponse> => {
        const { data } = await axios.put<SmartAnchorsResponse>(
            `${API_BASE}/api/v1/plan/${id}/smart-anchors`,
            { smart_anchors },
            { params: { token } },
        );
        return data;
    },
    toggleEventLock: async (
        token: string,
        id: string,
        day_number: number,
        event_number: number,
        is_locked: boolean,
    ): Promise<{ message?: string; status_code?: number }> => {
        const { data } = await axios.put(
            `${API_BASE}/api/v1/plan/${id}/events/lock`,
            { day_number, event_number, is_locked },
            { params: { token } },
        );
        return data;
    },
};
