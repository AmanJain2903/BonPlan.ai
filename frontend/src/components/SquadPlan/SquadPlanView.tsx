import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { api, Plan } from '../../apis/plan';

export default function SquadPlanView() {
  const { tripId } = useParams<{ tripId: string }>();
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);

  // Enforce auth & RBAC on mount
  useEffect(() => {
    if (!isLoggedIn) {
      navigate('/');
      return;
    }
    const checkAccess = async () => {
      try {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (!token || !tripId) return;

        // 1. Ensure user has 'owner' privileges
        const rbacRes = await api.getRBAC(token, tripId);
        if (!rbacRes.rbac || (rbacRes.rbac !== 'owner' && rbacRes.rbac !== 'group_member')) {
          navigate('/');
          return;
        }

        // 2. Fetch comprehensive Plan Data
        const planRes = await api.getPlan(token, tripId);
        if (planRes.plan) {
          setPlan(planRes.plan);
        } else {
          navigate('/');
        }
      } catch (err) {
        console.error("SquadPlanView access error:", err);
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    checkAccess();
  }, [isLoggedIn, navigate, tripId]);

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-10 flex items-center justify-center"
      >
        <div className="w-8 h-8 border-2 border-cyan/50 border-t-cyan rounded-full animate-spin" />
      </motion.div>
    );
  }

  if (!plan) return null;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9, filter: 'blur(10px)' }}
      animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className="fixed inset-0 z-10 w-full flex items-center justify-center"
    >
      <h1 className="text-4xl font-extrabold text-cyan tracking-widest uppercase">Coming Soon ...</h1>
    </motion.div>
  );
}
