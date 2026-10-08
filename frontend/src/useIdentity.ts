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
    chatApi.me()
      .then((me) => { if (!cancelled) setIdentity(me); })
      .catch(() => { if (!cancelled) setIdentity(undefined); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  return identity;
}
