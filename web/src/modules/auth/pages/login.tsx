"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import SkyImage from "@/assets/space.jpg";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useMutation } from "@tanstack/react-query";
import { endpoints } from "@/config/endpoints";
import { AuthServices } from "@/services";
import { useUserStore } from "@/store";

export function Login() {
  const router = useRouter();
  const { setUser } = useUserStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loginMutation = useMutation({
    mutationKey: [endpoints.auth.login.query],
    mutationFn: () => AuthServices.login(email, password),
    onSuccess: async () => {
      const me = await AuthServices.getMe();
      setUser(me.data.payload.user);
      router.push("/");
    },
    onError: () => {
      setError("Invalid email or password.");
    },
  });

  return (
    <main className="flex min-h-dvh w-full items-center justify-between">
      <div className="flex w-1/2 flex-col items-center justify-center gap-4 px-8">
        <h1 className="text-2xl font-semibold">Compliance Navigator</h1>
        <p className="text-muted-foreground text-center text-sm">
          Sign in to save roadmaps. Public compliance data does not require an
          account.
        </p>

        <form
          className="flex w-full max-w-sm flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            loginMutation.mutate();
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          <Button type="submit" loading={loginMutation.isPending} size="lg">
            Sign in
          </Button>
        </form>

        <p className="text-muted-foreground text-sm">
          No account?{" "}
          <Link href="/register" className="text-primary underline">
            Create one
          </Link>
        </p>
      </div>
      <div className="relative h-screen w-1/2">
        <Image src={SkyImage} alt="Background" fill className="object-cover" />
      </div>
    </main>
  );
}
