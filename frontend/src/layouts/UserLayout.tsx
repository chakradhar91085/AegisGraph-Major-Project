import { MessageSquare, Plus, ShieldCheck } from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import { ADMIN_ROLE } from '../api';
import { useIdentity } from '../useIdentity';
import { Shell } from './Shell';

export function UserLayout() {
  const { messages, endActiveSession } = useChat();
  const identity = useIdentity();

  const sections = [{ title: 'Knowledge', items: [{ to: '/app', label: 'Workspace', icon: MessageSquare, end: true }] }];
  if (identity?.role === ADMIN_ROLE) {
    sections.push({ title: 'Admin', items: [{ to: '/admin', label: 'Admin dashboard', icon: ShieldCheck, end: false }] });
  }

  return (
    <Shell
      sections={sections}
      actions={
        <button
          onClick={endActiveSession}
          disabled={messages.length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-blue-500/60 hover:bg-slate-800 disabled:opacity-50"
          title="End this conversation and start a fresh one"
        >
          <Plus className="h-4 w-4" /> New chat
        </button>
      }
    />
  );
}
