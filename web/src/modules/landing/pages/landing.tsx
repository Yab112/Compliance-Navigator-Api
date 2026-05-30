"use client";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useUserStore } from "@/store";
import { useMutation } from "@tanstack/react-query";
import { endpoints } from "@/config";
import { AuthServices } from "@/services";

export function LandingPage() {
  const { user, setUser } = useUserStore();

  const logoutMutation = useMutation({
    mutationKey: [endpoints.auth.logout.query],
    mutationFn: AuthServices.logout,
    onSuccess: () => {
      setUser(null);
    },
  });

  return (
    <main className={"flex items-center justify-center min-h-dvh"}>
      <div className={"flex items-center gap-2 flex-col"}>
        <h1>This is your landing page</h1>

        {user ? (
          <div>
            <h1>Welcome, {user.fullname}</h1>

            <Button onClick={() => logoutMutation.mutate()} loading={logoutMutation.isPending}>
              Logout
            </Button>
          </div>
        ) : (
          <Link href={"/login"}>
            <Button>Login</Button>
          </Link>
        )}
      </div>
    </main>
  );
}
