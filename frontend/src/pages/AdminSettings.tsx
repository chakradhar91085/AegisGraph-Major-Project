import { useState } from 'react';
import axios from 'axios';
import { BellRing } from 'lucide-react';
import { auditApi } from '../api';
import { usePolling } from '../usePolling';
import { PageHeader, Card, ErrorNote } from '../components/AdminUi';

export function AdminSettings() {
  const { data: channels, error } = usePolling(() => auditApi.alertChannels(), 60000);
  const [result, setResult] = useState<string | null>(null);

  const sendTestAlert = async () => {
    setResult('Sending…');
    try {
      const results = await auditApi.sendTestAlert();
      setResult(Object.entries(results).map(([ch, r]) => `${ch}: ${r}`).join(' · '));
    } catch (err) {
      setResult((axios.isAxiosError(err) && err.response?.data?.detail) || 'Test alert failed.');
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <PageHeader title="Settings" subtitle="Alert channels and how roles are assigned" />
      <ErrorNote text={error} />
      <div className="grid max-w-5xl gap-4 p-6 lg:grid-cols-2">
        <Card title="Security alerts">
          <div className="space-y-3 p-4 text-sm text-slate-300">
            <p>
              Admins are alerted when a user's policy escalates (normal → masking → blocked) and on every prompt-injection or bulk personal-data request.
            </p>
            <p>
              Channels on: <span className="font-mono text-slate-100">{channels === null ? '…' : channels.length ? channels.join(' + ') : 'none configured'}</span>
            </p>
            <p className="text-xs text-slate-400">Turn channels on with TELEGRAM_* and SMTP_* in backend/.env.</p>
            <button
              onClick={sendTestAlert}
              disabled={!channels?.length}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            >
              <BellRing className="h-4 w-4" /> Send test alert
            </button>
            {result && <p className="text-xs text-slate-400" role="status">{result}</p>}
          </div>
        </Card>

        <Card title="Roles">
          <div className="space-y-3 p-4 text-sm text-slate-300">
            <p>Roles are set on the server only. Nobody can pick their own role from the browser.</p>
            <ul className="space-y-1.5">
              <li><span className="font-mono text-slate-100">Auditor</span>: admin dashboard, up to 50 records and depth 5</li>
              <li><span className="font-mono text-slate-100">Analyst</span>: up to 30 records and depth 3</li>
              <li><span className="font-mono text-slate-100">Standard</span>: everyone else, up to 10 records and depth 2</li>
            </ul>
            <p className="text-xs text-slate-400">
              To change a role, add <span className="font-mono">clerk_user_id:Role</span> to SECURITY_USER_ROLES in backend/.env and restart the backend.
              Users can copy their id from the sidebar.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
