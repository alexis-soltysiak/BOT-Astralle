"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { getAuthSession } from "@/features/auth/api";
import { ApiUnauthorizedError } from "@/features/api/client";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const session = useQuery({
    queryKey: ["auth-session"],
    queryFn: getAuthSession,
    retry: false,
  });

  React.useEffect(() => {
    if (session.error instanceof ApiUnauthorizedError) {
      const next = encodeURIComponent(pathname || "/admin");
      router.replace(`/login?next=${next}`);
    }
  }, [pathname, router, session.error]);

  if (session.isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="rounded-2xl border border-white/10 bg-black/20 px-6 py-4 text-sm text-slate-300">
          Verification de la session...
        </div>
      </div>
    );
  }

  if (session.error) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-6 py-4 text-sm text-red-200">
          Impossible de verifier la session admin.
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
