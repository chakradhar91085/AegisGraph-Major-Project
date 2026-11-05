import { useEffect, useState } from 'react';
import { chatApi } from './api';
import type { Identity } from './api';

/**
 * The signed-in user's server-assigned role and current risk.
 * `null` while loading; `undefined` if the backend could not be reached.
 * Refetches whenever `refreshKey` changes (e.g. after each chat answer).
 */
export function useIdentity(refreshKey: unknown = null): Identity | null | undefined {
  const [identity, setIdentity] = useState<Identity | null | undefined>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // One retry: a sign-in token that expired while the tab sat idle fails the
    // first call, and Clerk has a fresh one a moment later.
    const load = (retry: boolean) => chatApi.me()
      .then((me) => { if (!cancelled) setIdentity(me); })
      .catch(() => {
        if (cancelled) return;
        if (retry) timer = setTimeout(() => load(false), 1500);
        else setIdentity(undefined);
      });
    load(true);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [refreshKey]);

  return identity;
}
