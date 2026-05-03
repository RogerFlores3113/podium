"use client";

import { SignIn } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SignInPage() {
  const router = useRouter();

  const handleGuestSession = async () => {
    try {
      const res = await fetch(`${API_URL}/guest/session`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to create guest session");
      const { token, expires_at } = await res.json();
      sessionStorage.setItem("podium_guest_token", token);
      sessionStorage.setItem("podium_guest_expires", expires_at);
      router.push("/");
    } catch (err) {
      console.error("Guest session error:", err);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6">
      <SignIn />
      <div className="flex flex-col items-center gap-2">
        <button
          onClick={handleGuestSession}
          className="text-sm text-gray-500 hover:text-gray-700 underline underline-offset-2"
        >
          Try as guest — no sign-up required
        </button>
        <p className="text-xs text-gray-400">Guest sessions expire in 24 hours</p>
      </div>
    </div>
  );
}
