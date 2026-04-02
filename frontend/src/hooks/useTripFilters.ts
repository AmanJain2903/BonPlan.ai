import { useMemo } from 'react';
import { Plan } from '../apis/plan';

export const useDraftPlans = (plans: Plan[]) => {
    return useMemo(() => {
        if (!plans || plans.length === 0) return [];

        return plans.filter(plan =>
            plan.is_draft === true &&
            plan.role === 'owner' &&
            plan.planning_type === 'solo'
        );
    }, [plans]);
};
