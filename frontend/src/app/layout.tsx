"use client";

import "./globals.css";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "@/shared/ui/sidebar";

const queryClient = new QueryClient();

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <QueryClientProvider client={queryClient}>
          <div className="relative min-h-screen overflow-hidden">
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-secondary/20 blur-3xl" />
              <div className="absolute right-0 top-0 h-80 w-80 rounded-full bg-primary/15 blur-3xl" />
              <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
            </div>

            <div className="relative flex min-h-screen flex-col md:flex-row">
              <Sidebar />
              <main className="flex-1 p-4 md:p-8">
                <div className="mx-auto max-w-7xl">{children}</div>
              </main>
            </div>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
