import { Link } from 'react-router-dom';
import Footer from '../HomePage/Footer';

interface Props {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}

export default function LegalPage({ title, lastUpdated, children }: Props) {
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 px-6 lg:px-12 xl:px-20 py-20 z-10">
        <div className="max-w-3xl mx-auto">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-xs text-white/40 hover:text-cyan transition-colors duration-200 mb-10"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to BonPlan.ai
          </Link>

          <div className="mb-10 border-b border-white/8 pb-8">
            <h1 className="text-3xl font-semibold text-white mb-2">{title}</h1>
            <p className="text-xs text-white/35">Last updated: {lastUpdated}</p>
          </div>

          <div className="space-y-8 text-white/70 text-sm leading-relaxed">
            {children}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
