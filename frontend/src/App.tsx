import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Navbar from './components/shared/Navbar';
import ScrollManager from './components/shared/ScrollManager';
import Hero from './components/HomePage/Hero';
import Features from './components/HomePage/Features';
import DraftPlansComponent from './components/HomePage/DraftPlansComponent';
import PersonalPlansComponent from './components/HomePage/PersonalPlansComponent';
import Footer from './components/HomePage/Footer';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import VerifyEmail from './components/Auth/VerifyEmail';
import GoogleAuthCallback from './components/Auth/GoogleAuthCallback';
import ForgotPassword from './components/Auth/ForgotPassword';
import ResetPassword from './components/Auth/ResetPassword';
import ShareInvite from './components/Auth/ShareInvite';
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
import AdminLayout from './components/Admin/AdminLayout';
import AnalyticsDashboard from './components/Admin/Pages/AnalyticsDashboard';
import SkuManager from './components/Admin/Pages/SkuManager';
import UsageViewer from './components/Admin/Pages/UsageViewer';
import FaqManager from './components/Admin/Pages/FaqManager';
import SupportTickets from './components/Admin/Pages/SupportTickets';
import PrivacyPolicy from './components/Legal/PrivacyPolicy';
import TermsOfService from './components/Legal/TermsOfService';
import PublicTripView from './components/PublicTripView/PublicTripView';
import SEOHead from './components/shared/SEOHead';


function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, isAdmin } = useAuth();
  const location = useLocation();

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!isAdmin) {
    return <Navigate to="/" />;
  }

  return children;
}


function HomePageSEO() {
  return (
    <SEOHead
      title="AI Travel Planner — Tell us When. We Tell the How."
      description="BonPlan.ai builds personalized, agent-generated travel itineraries in minutes. From flights to hidden gems, your perfect trip starts here."
      url="/"
    />
  );
}

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
      } catch {
        // Do nothing
      } finally {
        setIsFetchingPlans(false);
      }
    };
    fetchPlans();
  }, [isLoggedIn]);

  const handlePlanDelete = useCallback((id: string) => {
    setPlans(prev => prev.filter(p => p.id !== id));
  }, []);

  return (
    <>
      <HomePageSEO />
      <main className="relative w-full min-h-screen pt-[24px]">
        <Hero plans={plans} isLoadingPlans={isFetchingPlans} />
        {plans.length > 0 && <DraftPlansComponent plans={plans} onDelete={handlePlanDelete} />}
        {plans.length > 0 && <PersonalPlansComponent plans={plans} onDelete={handlePlanDelete} />}
        {plans.length > 0 && <PersonalPlansComponent plans={plans} variant="shared" onDelete={handlePlanDelete} />}
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
        <Route path="/trip/:tripId" element={<PublicTripView />} />
        <Route path="/login" element={<><SEOHead title="Sign In" description="Sign in to BonPlan.ai and access your AI-generated travel itineraries." url="/login" noIndex /><Login /></>} />
        <Route path="/register" element={<><SEOHead title="Get Started" description="Create your free BonPlan.ai account and start planning your next trip with AI in minutes." url="/register" noIndex /><Register /></>} />
        <Route path="/auth/google/callback" element={<GoogleAuthCallback />} />
        <Route path="/verify-email" element={<><SEOHead title="Verify Email" noIndex /><VerifyEmail /></>} />
        <Route path="/share-invite" element={<><SEOHead title="Trip Invitation" noIndex /><ShareInvite /></>} />
        <Route path="/forgot-password" element={<><SEOHead title="Reset Password" noIndex /><ForgotPassword /></>} />
        <Route path="/reset-password" element={<><SEOHead title="Reset Password" noIndex /><ResetPassword /></>} />
        <Route path="/account/:section?" element={<><SEOHead title="My Account" noIndex /><AccountLayout /></>} />
        <Route path="/draft-plan" element={<><SEOHead title="Plan a Trip" noIndex /><PlanSetup /></>} />
        <Route path="/plan/solo/:tripId" element={<><SEOHead title="My Itinerary" noIndex /><SoloPlanView /></>} />
        <Route path="/plan/squad/:tripId" element={<><SEOHead title="Squad Itinerary" noIndex /><SquadPlanView /></>} />
        <Route
          path="/admin"
          element={(
            <ProtectedRoute>
              <AdminLayout />
            </ProtectedRoute>
          )}
        >
          <Route index element={<Navigate to="analytics" replace />} />
          <Route path="analytics" element={<AnalyticsDashboard />} />
          <Route path="skus" element={<SkuManager />} />
          <Route path="usage" element={<UsageViewer />} />
          <Route path="faq" element={<FaqManager />} />
          <Route path="tickets" element={<SupportTickets />} />
        </Route>
        <Route path="/privacy" element={<><SEOHead title="Privacy Policy" description="Read the BonPlan.ai Privacy Policy to learn how we handle your data." url="/privacy" /><PrivacyPolicy /></>} />
        <Route path="/terms" element={<><SEOHead title="Terms of Service" description="Review the BonPlan.ai Terms of Service." url="/terms" /><TermsOfService /></>} />
        <Route path="/rate-limits/skus" element={<Navigate to="/admin/skus" replace />} />
        <Route path="/rate-limits/usage" element={<Navigate to="/admin/usage" replace />} />
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
