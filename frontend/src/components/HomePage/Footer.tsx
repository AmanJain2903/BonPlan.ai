import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="relative border-t border-white/5 px-6 lg:px-12 xl:px-20 py-12">
      <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-5">
          <Link to="/privacy" className="text-xs text-white/35 hover:text-cyan transition-colors duration-200">
            Privacy Policy
          </Link>
          <Link to="/terms" className="text-xs text-white/35 hover:text-cyan transition-colors duration-200">
            Terms of Service
          </Link>
        </div>

        <p className="text-xs text-white/25">
          &copy; {new Date().getFullYear()} BonPlan.ai &mdash; All rights reserved.
        </p>
      </div>
    </footer>
  );
}
