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

export function Register() {
  const router = useRouter();
  const [fullname, setFullname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const registerMutation = useMutation({
    mutationKey: [endpoints.auth.register.query],
    mutationFn: () =>
      AuthServices.register({ email, password, fullname }),
    onSuccess: () => {
      router.push("/login");
    },
    onError: () => {
      setError("Could not create account. Email may already be in use.");
    },
  });

  return (
    <main className="flex min-h-dvh w-full items-center justify-between">
      <div className="flex w-1/2 flex-col items-center justify-center gap-4 px-8">
        <h1 className="text-2xl font-semibold">Create account</h1>

        <form
          className="flex w-full max-w-sm flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            registerMutation.mutate();
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="fullname">Full name</Label>
            <Input
              id="fullname"
              required
              value={fullname}
              onChange={(e) => setFullname(e.target.value)}
            />
          </div>
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
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          <Button type="submit" loading={registerMutation.isPending} size="lg">
            Register
          </Button>
        </form>

        <p className="text-muted-foreground text-sm">
          Already have an account?{" "}
          <Link href="/login" className="text-primary underline">
            Sign in
          </Link>
        </p>
      </div>
      <div className="relative h-screen w-1/2">
        <Image src={SkyImage} alt="Background" fill className="object-cover" />
      </div>
    </main>
  );
}
