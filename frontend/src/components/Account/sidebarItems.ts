import { UserCircle, SlidersHorizontal, Plug, Bell, Settings, Headset } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type SidebarItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  section: number;
};

export const sidebarItems: SidebarItem[] = [
  { key: 'profile', label: 'My Profile', icon: UserCircle, section: 1 },
  { key: 'preferences', label: 'Preferences', icon: SlidersHorizontal, section: 1 },
  { key: 'integrations', label: 'Integrations', icon: Plug, section: 1 },
  { key: 'notifications', label: 'Notifications', icon: Bell, section: 2 },
  { key: 'settings', label: 'Settings', icon: Settings, section: 2 },
  { key: 'support', label: 'Support', icon: Headset, section: 3 },
];
