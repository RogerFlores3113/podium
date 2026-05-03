"use client";

import { useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

export function useAuthFetch() {
  const { getToken } = useAuth();

  return useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const token = await getAuthToken(getToken);
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${token}`,
        },
      });
    },
    [getToken],
  );
}

async function getAuthToken(
  getClerkToken: () => Promise<string | null>,
): Promise<string | null> {
  try {
    const guestToken = sessionStorage.getItem("podium_guest_token");
    const guestExpires = sessionStorage.getItem("podium_guest_expires");
    if (guestToken && guestExpires && new Date(guestExpires) > new Date()) {
      return guestToken;
    }
  } catch {
    // sessionStorage unavailable (SSR or private browsing) — fall through
  }
  return getClerkToken();
}
