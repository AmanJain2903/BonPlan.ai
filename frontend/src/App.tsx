import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/shared/Navbar';
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
import { AuthProvider, useAuth } from './context/AuthContext';
import { api, DraftPlan } from './apis/planDraft';
import WorldMapBackground from './components/shared/WorldMapBackground';
import BlurBackground from './components/shared/blurBackground';
import { TripProvider } from './context/TripContext';
import TripFlushOnHome from './components/shared/TripFlushOnHome';


function HomePage() {
  const { isLoggedIn } = useAuth();
  const [draftPlans, setDraftPlans] = useState<DraftPlan[]>([]);

  useEffect(() => {
    const fetchDraftPlans = async () => {
      if (!isLoggedIn) {
        setDraftPlans([]);
        return;
      }
      try {
        const token = localStorage.getItem('token');
        if (token) {
          const response = await api.getDraftPlans(token);
          if (response.draft_plans) {
            setDraftPlans(response.draft_plans);
          }
        }
      } catch (error) {
        console.error("Failed to fetch draft plans:", error);
      }
    };
    fetchDraftPlans();
  }, [isLoggedIn]);

  return (
    <>
      <main className="relative w-full min-h-screen pt-[24px]">
        <Hero draftPlans={draftPlans} />
        {draftPlans.length > 0 && <DraftPlansComponent plans={draftPlans} />}
        <Features />
      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <WorldMapBackground />
      <BlurBackground />
      <AuthProvider>
        <TripProvider>
          <TripFlushOnHome />
          <Navbar />
          <div className="min-h-screen bg-midnight">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/account/:section?" element={<AccountLayout />} />
              <Route path="/draft-plan" element={<PlanSetup />} />
            </Routes>
          </div>
        </TripProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
