import { Activity, BarChart3, HelpCircle, Shield, Ticket } from 'lucide-react';

export type AdminNavItem = { name: string; href: string; icon: React.ElementType };

export const adminSections: { label: string; items: AdminNavItem[] }[] = [
  {
    label: 'Overview',
    items: [
      { name: 'Analytics', href: '/admin/analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Rate Limiting',
    items: [
      { name: 'SKU Management', href: '/admin/skus', icon: Shield },
      { name: 'Usage Viewer', href: '/admin/usage', icon: Activity },
    ],
  },
  {
    label: 'Support',
    items: [
      { name: 'FAQ Manager', href: '/admin/faq', icon: HelpCircle },
      { name: 'Support Tickets', href: '/admin/tickets', icon: Ticket },
    ],
  },
];
