import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/HomePage/Navbar';
import Hero from './components/HomePage/Hero';
import Features from './components/HomePage/Features';
import Footer from './components/HomePage/Footer';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import VerifyEmail from './components/Auth/VerifyEmail';
import ForgotPassword from './components/Auth/ForgotPassword';
import ResetPassword from './components/Auth/ResetPassword';
import AccountLayout from './components/Account/AccountLayout';
import { AuthProvider } from './context/AuthContext';

function HomePage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Features />
      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen bg-midnight">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/account/:section?" element={<AccountLayout />} />
          </Routes>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
