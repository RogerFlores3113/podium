"use client";

import { useAuth } from "@clerk/nextjs";
import ChatPage from "@/app/components/ChatPage";
import LandingPage from "@/app/components/LandingPage";

function AuthSkeleton() {
  return <div className="h-screen w-full" style={{ background: "var(--bg-base)" }} />;
}

export default function Home() {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) return <AuthSkeleton />;
  if (!isSignedIn) return <LandingPage />;
  return <ChatPage />;
}
