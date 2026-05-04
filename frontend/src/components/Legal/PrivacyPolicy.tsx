import LegalPage from './LegalPage';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-base font-semibold text-white mb-3">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-white/65 text-sm leading-relaxed">{children}</p>;
}

function Ul({ items }: { items: string[] }) {
  return (
    <ul className="list-none space-y-1.5 pl-0">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-white/65 text-sm">
          <span className="mt-1.5 w-1 h-1 rounded-full bg-cyan/60 flex-shrink-0" />
          {item}
        </li>
      ))}
    </ul>
  );
}

export default function PrivacyPolicy() {
  return (
    <LegalPage title="Privacy Policy" lastUpdated="May 3, 2026">
      <Section title="1. Introduction">
        <P>
          BonPlan.ai ("we", "us", "our") is an AI-powered travel planning platform. This Privacy Policy explains how we collect,
          use, store, and protect your personal information when you use our service at bonplan.ai.
        </P>
        <P>
          By creating an account or using BonPlan.ai, you agree to the practices described in this policy. If you do not agree,
          please do not use our service.
        </P>
      </Section>

      <Section title="2. Information We Collect">
        <P>We collect the following categories of data:</P>
        <Ul items={[
          'Account data: your name, email address, and password (hashed) when you register directly, or your name, email, and profile picture when you sign in with Google OAuth.',
          'Trip data: destinations, travel dates, group size, preferences, budget, and all itinerary content you generate or edit through the platform.',
          'Usage data: pages visited, features used, plan generation counts, and timestamps — used to enforce rate limits and improve the product.',
          'Support data: messages and attachments you submit through our support form.',
          'Technical data: IP address, browser type, and device information collected automatically via server logs.',
        ]} />
      </Section>

      <Section title="3. How We Use Your Data">
        <P>We use your information to:</P>
        <Ul items={[
          'Generate and store your travel itineraries using our AI planning engine.',
          'Authenticate your identity and maintain your session.',
          'Enforce per-user rate limits to ensure fair access to AI generation.',
          'Respond to support requests and resolve issues.',
          'Send transactional emails (e.g. email verification, password reset). We do not send marketing emails without explicit opt-in.',
          'Improve the quality of our AI models and product features using anonymised, aggregated usage patterns.',
        ]} />
        <P>
          We do not sell, rent, or trade your personal data to any third party for their own marketing or commercial purposes.
        </P>
      </Section>

      <Section title="4. Third-Party Services">
        <P>BonPlan.ai integrates with the following third-party services, each with their own privacy policies:</P>
        <Ul items={[
          'Google OAuth — used for "Sign in with Google". We receive your name, email, and profile picture from Google. We do not receive or store your Google password.',
          'Google Places API — used to search and display destination and venue information in your itineraries.',
          'Google Gemini AI — our AI planning engine sends your trip preferences and destination information to Gemini to generate itinerary content. No personally identifying information beyond trip context is sent.',
          'Google Maps — used for route and distance calculations within itineraries.',
          'PostgreSQL (self-hosted) — all structured data is stored in our own database, not in any third-party cloud database service.',
        ]} />
      </Section>

      <Section title="5. Data Storage & Security">
        <P>
          Your data is stored in a PostgreSQL database hosted on our infrastructure. All data in transit is encrypted via HTTPS/TLS.
          Passwords are hashed using bcrypt and never stored in plain text. Google OAuth tokens are stored encrypted at rest.
        </P>
        <P>
          We implement rate limiting, session expiry, and access controls to protect your account. However, no system is
          perfectly secure — if you believe your account has been compromised, contact us immediately.
        </P>
      </Section>

      <Section title="6. Data Retention & Deletion">
        <P>
          We retain your account and trip data for as long as your account is active. If you delete your account through the
          account settings page, all personal data, trip itineraries, support tickets, and associated records are permanently
          deleted from our systems within 30 days.
        </P>
        <P>
          Anonymised, aggregated usage statistics that cannot be linked back to you may be retained for analytical purposes.
        </P>
      </Section>

      <Section title="7. Cookies & Local Storage">
        <P>
          BonPlan.ai uses browser localStorage and sessionStorage to store your authentication token after login. We do not use
          third-party tracking cookies or advertising cookies. No cookie consent banner is required as we do not deploy
          non-essential cookies.
        </P>
      </Section>

      <Section title="8. Your Rights">
        <P>Depending on your jurisdiction, you may have the right to:</P>
        <Ul items={[
          'Access the personal data we hold about you.',
          'Request correction of inaccurate data.',
          'Request deletion of your data (right to erasure).',
          'Object to or restrict certain processing of your data.',
          'Data portability — request an export of your trip data.',
        ]} />
        <P>
          To exercise any of these rights, contact us at the address below. We will respond within 30 days.
        </P>
      </Section>

      <Section title="9. Children's Privacy">
        <P>
          BonPlan.ai is not directed at children under the age of 13. We do not knowingly collect personal data from children.
          If you believe a child has created an account, contact us and we will delete it promptly.
        </P>
      </Section>

      <Section title="10. Changes to This Policy">
        <P>
          We may update this Privacy Policy from time to time. When we do, we will update the "Last updated" date at the top of
          this page. Continued use of BonPlan.ai after changes constitutes acceptance of the updated policy.
        </P>
      </Section>

      <Section title="11. Contact">
        <P>
          For privacy-related questions, data requests, or concerns, contact us at:{' '}
          <a href="mailto:support@bonplan.ai" className="text-cyan hover:underline">
            support@bonplan.ai
          </a>
        </P>
      </Section>
    </LegalPage>
  );
}
