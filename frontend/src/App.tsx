import Navbar from './components/HomePage/Navbar';
import Hero from './components/HomePage/Hero';
import Features from './components/HomePage/Features';
import Footer from './components/HomePage/Footer';

export default function App() {
  return (
    <div className="min-h-screen bg-midnight">
      <Navbar />
      <main>
        <Hero />
        <Features />
      </main>
      <Footer />
    </div>
  );
}
