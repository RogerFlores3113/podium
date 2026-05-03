"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import ChatPage from "@/app/components/ChatPage";
import LandingPage from "@/app/components/LandingPage";

function AuthSkeleton() {
  return <div className="h-screen w-full" style={{ background: "var(--bg-base)" }} />;
}

export default function Home() {
  const { isSignedIn, isLoaded } = useAuth();
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    try {
      const token = sessionStorage.getItem("podium_guest_token");
      const expires = sessionStorage.getItem("podium_guest_expires");
      if (token && expires && new Date(expires) > new Date()) {
        setIsGuest(true);
      }
    } catch {
      // sessionStorage unavailable
    }
  }, []);

  if (!isLoaded) return <AuthSkeleton />;
  if (isSignedIn || isGuest) return <ChatPage />;
  return <LandingPage />;
}
