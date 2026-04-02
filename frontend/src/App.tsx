import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Navbar from './components/shared/Navbar';
import ScrollManager from './components/shared/ScrollManager';
import Hero from './components/HomePage/Hero';
import Features from './components/HomePage/Features';
import DraftPlansComponent from './components/HomePage/DraftPlansComponent';
import Footer from './components/HomePage/Footer';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import VerifyEmail from './components/Auth/VerifyEmail';
import ForgotPassword from './components/Auth/ForgotPassword';
import ResetPassword from './components/Auth/ResetPassword';
import AccountLayout from './components/Account/AccountLayout';
import PlanSetup from './components/DraftPlan/PlanSetup';
import SoloPlanView from './components/SoloPlan/SoloPlanView';
import SquadPlanView from './components/SquadPlan/SquadPlanView';
import { AuthProvider, useAuth } from './context/AuthContext';
import { api, Plan } from './apis/plan';
import WorldMapBackground from './components/shared/WorldMapBackground';
import BlurBackground from './components/shared/blurBackground';
import { TripProvider } from './context/TripContext';
import TripFlushOnHome from './components/shared/TripFlushOnHome';


function HomePage() {
  const { isLoggedIn } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [isFetchingPlans, setIsFetchingPlans] = useState(true);

  useEffect(() => {
    const fetchPlans = async () => {
      setIsFetchingPlans(true);
      if (!isLoggedIn) {
        setPlans([]);
        setIsFetchingPlans(false);
        return;
      }
      try {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (token) {
          const response = await api.getPlans(token);
          if (response.plans) {
            setPlans(response.plans);
          }
        }
      } catch (error) {
        console.error("Failed to fetch draft plans:", error);
      } finally {
        setIsFetchingPlans(false);
      }
    };
    fetchPlans();
  }, [isLoggedIn]);

  return (
    <>
      <main className="relative w-full min-h-screen pt-[24px]">
        <Hero plans={plans} isLoadingPlans={isFetchingPlans} />
        {plans.length > 0 && <DraftPlansComponent plans={plans} />}
        <Features />
      </main>
      <Footer />
    </>
  );
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/account/:section?" element={<AccountLayout />} />
        <Route path="/draft-plan" element={<PlanSetup />} />
        <Route path="/plan/solo/:tripId" element={<SoloPlanView />} />
        <Route path="/plan/squad/:tripId" element={<SquadPlanView />} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollManager />
      <WorldMapBackground />
      <BlurBackground />
      <AuthProvider>
        <TripProvider>
          <TripFlushOnHome />
          <Navbar />
          <div className="min-h-screen">
            <AnimatedRoutes />
          </div>
        </TripProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
