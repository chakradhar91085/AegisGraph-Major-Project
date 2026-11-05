import { useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ClerkLoading, SignedIn, SignedOut, RedirectToSignIn, useAuth } from '@clerk/clerk-react';
import { setTokenGetter } from './api';
import { LandingPage } from './pages/LandingPage';
import { UserLayout } from './layouts/UserLayout';
import { AdminLayout } from './layouts/AdminLayout';
import { AdminGate } from './components/AdminGate';
import { QueryPlayground } from './pages/QueryPlayground';
import { AdminOverview } from './pages/AdminOverview';
import { SystemLogs } from './pages/SystemLogs';
import { ChatProvider, useChat } from './contexts/ChatContext';
import { AdminUser } from './pages/AdminUser';
import { AdminSettings } from './pages/AdminSettings';

// Hands the Clerk session token to the API client. Rendered before the router so
// it is registered before any page makes its first request. Also wipes the chat
// when the signed-in user changes, so the next person on this browser never
// sees the previous user's conversation.
function AuthBridge() {
  const { getToken, userId } = useAuth();
  const { resetConversation } = useChat();
  const lastUserId = useRef(userId);

  useEffect(() => {
    setTokenGetter(() => getToken());
  }, [getToken]);

  useEffect(() => {
    if (lastUserId.current && lastUserId.current !== userId) resetConversation();
    lastUserId.current = userId;
  }, [userId, resetConversation]);

  return null;
}

// Shows a loading screen while Clerk checks the session, instead of a blank page.
function RequireSignIn({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ClerkLoading>
        <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-500 text-sm font-mono">
          Checking your sign-in...
        </div>
      </ClerkLoading>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}

function App() {
  return (
    <ChatProvider>
      <AuthBridge />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />

        {/* Chat: every signed-in user, Auditors included. */}
        <Route path="/app" element={<RequireSignIn><UserLayout /></RequireSignIn>}>
          <Route index element={<QueryPlayground />} />
        </Route>

        {/* Admin dashboard: cross-user risk feed + audit log. Auditors only. */}
        <Route path="/admin" element={<RequireSignIn><AdminGate><AdminLayout /></AdminGate></RequireSignIn>}>
          <Route index element={<AdminOverview />} />
          <Route path="users/:userId" element={<AdminUser />} />
          <Route path="logs" element={<SystemLogs />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        {/* Fallback to landing page for unknown routes */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </ChatProvider>
  );
}

export default App;
