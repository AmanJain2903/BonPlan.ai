import { useMemo } from 'react';
import { Plan } from '../apis/plan';

const getStartTimestamp = (plan: Plan): number => {
    if (!plan.start_date) return Infinity;
    if (typeof plan.start_date === 'object' && plan.start_date.utcTimestamp != null) {
        return Number(plan.start_date.utcTimestamp);
    }
    return Infinity;
};

const sortByDate = (plans: Plan[]): Plan[] =>
    [...plans].sort((a, b) => getStartTimestamp(a) - getStartTimestamp(b));

export const useDraftPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        const filtered = plans.filter(plan =>
            (plan.status === "draft" || plan.status === "generating") &&
            plan.role === 'owner' &&
            plan.planning_type === 'solo'
        );
        return sortByDate(filtered);
    }, [plans]);
};

export const usePersonalPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        const filtered = plans.filter(plan =>
            (plan.status !== "draft" && plan.status !== "generating") &&
            plan.role === 'owner' &&
            plan.planning_type === 'solo'
        );

        const active = sortByDate(filtered.filter(p => p.status !== 'completed'));
        const completed = sortByDate(filtered.filter(p => p.status === 'completed'));
        return [...active, ...completed];
    }, [plans]);
};

export const useSharedPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        const filtered = plans.filter(plan =>
            (plan.status !== "draft" && plan.status !== "generating") &&
            (plan.role === 'shared_viewer' || plan.role === 'shared_editor') &&
            plan.planning_type === 'solo'
        );

        const active = sortByDate(filtered.filter(p => p.status !== 'completed'));
        const completed = sortByDate(filtered.filter(p => p.status === 'completed'));
        return [...active, ...completed];
    }, [plans]);
};
