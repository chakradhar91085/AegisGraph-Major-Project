import { Navigate } from 'react-router-dom';
import { ADMIN_ROLE } from '../api';
import { useIdentity } from '../useIdentity';

function FullScreenMessage({ text }: { text: string }) {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-500 text-sm font-mono px-6 text-center">
      {text}
    </div>
  );
}

// Only Auditors (the admin role, enforced again by the backend) may open /admin.
export function AdminGate({ children }: { children: React.ReactNode }) {
  const identity = useIdentity();

  if (identity === null) return <FullScreenMessage text="Loading..." />;
  if (identity === undefined) {
    return <FullScreenMessage text="Can't reach the AegisGraph server to check your role. Is the backend running on port 8001?" />;
  }
  if (identity.role !== ADMIN_ROLE) return <Navigate to="/app" replace />;
  return <>{children}</>;
}
