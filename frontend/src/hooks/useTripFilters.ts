import { useMemo } from 'react';
import { Plan } from '../apis/plan';

export const useDraftPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        return plans.filter(plan =>
            (plan.status === "draft" || plan.status === "generating") &&
            plan.role === 'owner' &&
            plan.planning_type === 'solo'
        );
    }, [plans]);
};

export const usePersonalPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        return plans.filter(plan =>
            (plan.status !== "draft" && plan.status !== "generating") &&
            plan.role === 'owner' &&
            plan.planning_type === 'solo'
        );
    }, [plans]);
};

export const useSharedPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        return plans.filter(plan =>
            (plan.status !== "draft" && plan.status !== "generating") &&
            (plan.role === 'shared_viewer' || plan.role === 'shared_editor') &&
            plan.planning_type === 'solo'
        );
    }, [plans]);
};
