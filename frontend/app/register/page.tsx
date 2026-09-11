"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AuthCard } from "@/components/AuthCard";
import { Button, Field, Input, Notice } from "@/components/ui";

export default function RegisterPage() {
  const router = useRouter();
  const { user, signIn } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError("Use at least 8 characters for the password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      signIn(await api.register({ name, email, password }));
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Create an account"
      lede="Reports stay private to your account."
      footer={
        <>
          Already registered? <Link href="/login" className="text-cobalt hover:underline">Sign in</Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Name">
          <Input autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Email">
          <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <Input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <Notice>{error}</Notice>}
        <Button type="submit" busy={busy} className="w-full">Create account</Button>
      </form>
    </AuthCard>
  );
}
