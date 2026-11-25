"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn, useSession } from "next-auth/react";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";
import { Atmosphere, Avatar, BrandMark } from "@/components/glass/Shell";
import { ErrorState, FieldLabel, Segmented, Spinner } from "@/components/glass/ui";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 23 23" className="h-5 w-5" aria-hidden>
      <path fill="#F25022" d="M1 1h10v10H1z" />
      <path fill="#7FBA00" d="M12 1h10v10H12z" />
      <path fill="#00A4EF" d="M1 12h10v10H1z" />
      <path fill="#FFB900" d="M12 12h10v10H12z" />
    </svg>
  );
}

const AUTH_ERRORS: Record<string, string> = {
  CredentialsSignin: "That username and password don't match. Check both and try again.",
  OAuthSignin: "The sign-in provider couldn't be reached. Try again in a moment.",
  OAuthCallback: "The provider sent you back without a valid sign-in. Try again.",
  OAuthAccountNotLinked: "This email is already linked to a different sign-in method.",
  AccessDenied: "Access was denied by the provider.",
  Configuration: "Sign-in isn't configured on this server yet.",
};

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const rawCallback = params.get("callbackUrl") || "/";
  const callbackUrl = rawCallback.startsWith("/") && !rawCallback.startsWith("//") ? rawCallback : "/";
  const { data: session, status } = useSession();
  const [mode, setMode] = useState<"signin" | "signup">(params.get("mode") === "signup" ? "signup" : "signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const initialError = params.get("error");
  const [error, setError] = useState<string | null>(initialError ? AUTH_ERRORS[initialError] ?? "Sign-in didn't complete. Try again." : null);
  const [notice, setNotice] = useState<string | null>(null);
  const [providers, setProviders] = useState<{ google: boolean; microsoft: boolean } | null>(null);

  useEffect(() => {
    fetch("/api/account/providers")
      .then((r) => r.json())
      .then((p) => setProviders({ google: Boolean(p.google), microsoft: Boolean(p.microsoft) }))
      .catch(() => setProviders({ google: false, microsoft: false }));
  }, []);

  const cleanUser = username.trim().toLowerCase();
  const usernameProblem = username && !/^[a-z0-9._-]{3,32}$/.test(cleanUser) ? "3–32 characters: lowercase letters, numbers, dots, dashes or underscores." : null;
  const passwordProblem = mode === "signup" && password && password.length < 8 ? "At least 8 characters." : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!username || !password) {
      setError("Enter your username and password.");
      return;
    }
    if (usernameProblem || passwordProblem) return;
    setBusy("credentials");
    try {
      if (mode === "signup") {
        const res = await fetch("/api/account/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: cleanUser, password, name: name.trim() }) });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          setError(body.error || "Couldn't create the account.");
          return;
        }
      }
      const result = await signIn("credentials", { redirect: false, username: cleanUser, password });
      if (!result || result.error) {
        setError(AUTH_ERRORS[result?.error || "CredentialsSignin"] ?? "Sign-in didn't complete.");
        return;
      }
      router.push(callbackUrl);
      router.refresh();
    } catch {
      setError("Sign-in didn't complete. Check that the dashboard server is running and try again.");
    } finally {
      setBusy(null);
    }
  };

  const oauth = async (provider: "google" | "azure-ad") => {
    setError(null);
    setNotice(null);
    const ready = provider === "google" ? providers?.google : providers?.microsoft;
    if (!ready) {
      setNotice(
        provider === "google"
          ? "Google sign-in isn't set up on this server yet. The project owner adds GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to frontend/.env.local (redirect URI: /api/auth/callback/google) and restarts."
          : "Microsoft sign-in isn't set up on this server yet. The project owner adds AZURE_AD_CLIENT_ID and AZURE_AD_CLIENT_SECRET to frontend/.env.local (redirect URI: /api/auth/callback/azure-ad) and restarts.",
      );
      return;
    }
    setBusy(provider);
    await signIn(provider, { callbackUrl });
  };

  return (
    <div className="relative min-h-screen">
      <Atmosphere />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1180px] flex-col gap-6 px-4 py-6 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-2.5" aria-label="Back to the dashboard">
            <BrandMark className="h-8 w-8" />
            <span className="text-[0.9375rem] font-semibold text-fg-1">Chennai Division</span>
          </Link>
          <Link href={callbackUrl} className="btn btn-quiet btn-sm">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Back without signing in
          </Link>
        </div>

        <div className="glass rise my-auto grid overflow-hidden !rounded-[24px] lg:grid-cols-[1fr_minmax(0,460px)]">
          <div className="relative hidden flex-col justify-between gap-10 overflow-hidden border-r border-line p-10 lg:flex">
            <div className="dots pointer-events-none absolute inset-0" aria-hidden />
            <div className="relative">
              <h1 className="max-w-[14ch] text-[3rem] font-semibold leading-[1.02] tracking-[-0.035em] text-fg-1">Sign in only if you want to.</h1>
              <p className="mt-5 max-w-[44ch] text-[1rem] leading-relaxed text-fg-2">
                Everything in the dashboard works as a guest. Signing in puts your name and avatar on the shift charts you hand over, and keeps you recognisable across sessions.
              </p>
            </div>
            <ul className="relative flex flex-col gap-3 text-[0.875rem] text-fg-2">
              {["Watch the division run live", "Compare FIFO with CP-SAT, train by train", "Hand over a signed 6-hour control chart"].map((t) => (
                <li key={t} className="flex items-center gap-3">
                  <span className="h-1.5 w-1.5 rounded-full bg-champagne" aria-hidden /> {t}
                </li>
              ))}
            </ul>
          </div>

          <div className="p-6 sm:p-10">
            {status === "authenticated" && session?.user ? (
              <div className="flex flex-col items-start gap-5">
                <Avatar name={session.user.name} image={session.user.image} size={56} />
                <div>
                  <h2 className="text-[1.5rem] font-semibold tracking-[-0.02em] text-fg-1">You're signed in as {session.user.name}</h2>
                  <p className="mt-2 text-[0.9375rem] text-fg-2">Your avatar now shows in the top bar.</p>
                </div>
                <Link href={callbackUrl} className="btn btn-primary">
                  Continue to the dashboard
                </Link>
              </div>
            ) : (
              <>
                <h2 className="text-[1.5rem] font-semibold tracking-[-0.02em] text-fg-1">{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
                <p className="mt-1.5 text-[0.9375rem] text-fg-2">{mode === "signin" ? "Sign in to put your name on exports." : "Takes ten seconds. No email needed."}</p>

                <Segmented
                  className="mt-6"
                  label="Sign in or create an account"
                  value={mode}
                  onChange={(v) => {
                    setMode(v);
                    setError(null);
                  }}
                  options={[
                    { value: "signin" as const, label: "Sign in" },
                    { value: "signup" as const, label: "Create account" },
                  ]}
                />

                <div className="mt-6 flex flex-col gap-3">
                  <button type="button" className="btn btn-secondary !justify-start !gap-3 !py-3 !text-[0.9375rem]" disabled={busy !== null} onClick={() => oauth("google")}>
                    {busy === "google" ? <Spinner /> : <GoogleIcon />} Continue with Google
                  </button>
                  <button type="button" className="btn btn-secondary !justify-start !gap-3 !py-3 !text-[0.9375rem]" disabled={busy !== null} onClick={() => oauth("azure-ad")}>
                    {busy === "azure-ad" ? <Spinner /> : <MicrosoftIcon />} Continue with Microsoft
                  </button>
                </div>
                {notice ? <p className="mt-3 rounded-[12px] border border-[rgba(242,180,90,0.35)] bg-[rgba(242,180,90,0.07)] p-3 text-[0.8125rem] leading-relaxed text-fg-1">{notice}</p> : null}

                <div className="my-6 flex items-center gap-3 text-[0.75rem] text-fg-3">
                  <span className="h-px flex-1 bg-line" /> or with a username <span className="h-px flex-1 bg-line" />
                </div>

                <form onSubmit={submit} noValidate className="flex flex-col gap-4">
                  {mode === "signup" ? (
                    <div>
                      <FieldLabel htmlFor="lg-name" hint="Optional">
                        Your name
                      </FieldLabel>
                      <input id="lg-name" className="field" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
                    </div>
                  ) : null}
                  <div>
                    <FieldLabel htmlFor="lg-user">Username</FieldLabel>
                    <input
                      id="lg-user"
                      className="field"
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      aria-invalid={Boolean(usernameProblem)}
                      aria-describedby={usernameProblem ? "lg-user-err" : undefined}
                    />
                    {usernameProblem ? (
                      <p id="lg-user-err" className="mt-1.5 text-[0.75rem] text-caution">
                        {usernameProblem}
                      </p>
                    ) : null}
                  </div>
                  <div>
                    <FieldLabel htmlFor="lg-pass">Password</FieldLabel>
                    <div className="relative">
                      <input
                        id="lg-pass"
                        className="field pr-11"
                        type={show ? "text" : "password"}
                        autoComplete={mode === "signin" ? "current-password" : "new-password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        aria-invalid={Boolean(passwordProblem)}
                        aria-describedby={passwordProblem ? "lg-pass-err" : undefined}
                      />
                      <button type="button" className="icon-btn absolute right-1 top-1/2 !h-8 !w-8 -translate-y-1/2" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"}>
                        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {passwordProblem ? (
                      <p id="lg-pass-err" className="mt-1.5 text-[0.75rem] text-caution">
                        {passwordProblem}
                      </p>
                    ) : null}
                  </div>
                  {error ? <ErrorState message={error} compact /> : null}
                  <button type="submit" className="btn btn-primary mt-1 !py-3" disabled={busy !== null}>
                    {busy === "credentials" ? <Spinner /> : null} {mode === "signin" ? "Sign in" : "Create account and sign in"}
                  </button>
                </form>

                <p className="mt-6 text-center text-[0.8125rem] text-fg-2">
                  <Link href={callbackUrl} className="text-champagne underline">
                    Continue as a guest
                  </Link>
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
