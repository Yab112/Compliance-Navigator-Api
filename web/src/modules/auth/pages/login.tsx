"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLogin } from "@/api/auth";
import { aboutProduct } from "@/content/about";
import { MOCK_EMAIL, MOCK_PASSWORD } from "@/lib/mock-auth";

export function Login() {
  const searchParams = useSearchParams();
  const returnTo = searchParams.get("returnTo") || "/roadmap";
  const { login, isLoggingIn } = useLogin();
  const [email, setEmail] = useState(MOCK_EMAIL);
  const [password, setPassword] = useState(MOCK_PASSWORD);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mx-auto flex max-w-md flex-col px-4 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Save roadmaps and return to your compliance path on{" "}
            {aboutProduct.name}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={async (e) => {
              e.preventDefault();
              setError(null);
              try {
                await login({ email, password }, returnTo);
              } catch {
                setError("Invalid email or password.");
              }
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
            {error && <p className="text-destructive text-sm">{error}</p>}
            <Button type="submit" loading={isLoggingIn}>
              Sign in
            </Button>
          </form>
          <p className="text-muted-foreground mt-4 text-center text-xs">
            Demo credentials are pre-filled for development.
          </p>
          <p className="text-muted-foreground mt-2 text-center text-sm">
            <Link href="/" className="text-primary underline">
              Continue without signing in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
