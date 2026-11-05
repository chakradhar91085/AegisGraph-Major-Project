import { Activity, MessageSquare, ScrollText, Settings } from 'lucide-react';
import { Shell } from './Shell';

export function AdminLayout() {
  return (
    <Shell
      badge="Admin"
      sections={[
        {
          title: 'Monitoring',
          items: [
            { to: '/admin', label: 'Overview', icon: Activity, end: true },
            { to: '/admin/logs', label: 'Audit log', icon: ScrollText },
            { to: '/admin/settings', label: 'Settings', icon: Settings },
          ],
        },
        { title: 'User side', items: [{ to: '/app', label: 'Workspace', icon: MessageSquare }] },
      ]}
    />
  );
}
