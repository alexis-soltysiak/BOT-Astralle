"use client";

import React from "react";
import { Suspense } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { getAuthSession, loginAdmin } from "@/features/auth/api";
import { ApiUnauthorizedError } from "@/features/api/client";

function LoginPageContent() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const nextParam = params.get("next");
  const next = nextParam && nextParam.startsWith("/") ? nextParam : "/admin";
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");

  const session = useQuery({
    queryKey: ["auth-session"],
    queryFn: getAuthSession,
    retry: false,
  });

  React.useEffect(() => {
    if (session.data?.authenticated) {
      router.replace(next);
    }
  }, [next, router, session.data]);

  const login = useMutation({
    mutationFn: () => loginAdmin(username, password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      router.replace(next);
    },
  });

  const errorMessage =
    login.error instanceof ApiUnauthorizedError
      ? "Identifiants invalides."
      : login.error instanceof Error
        ? login.error.message
        : session.error instanceof Error && !(session.error instanceof ApiUnauthorizedError)
          ? session.error.message
          : null;

  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Connexion admin</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Nom d'utilisateur"
              autoComplete="username"
            />
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Mot de passe"
              autoComplete="current-password"
            />
          </div>

          {errorMessage ? (
            <div className="text-sm text-destructive">{errorMessage}</div>
          ) : null}

          <Button
            className="w-full"
            onClick={() => login.mutate()}
            disabled={login.isPending || !username || !password}
          >
            {login.isPending ? "Connexion..." : "Se connecter"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[80vh] items-center justify-center">
          <div className="rounded-2xl border border-white/10 bg-black/20 px-6 py-4 text-sm text-slate-300">
            Chargement...
          </div>
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
