"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { BellRing, Clock3, Send } from "lucide-react";
import { apiGet } from "@/features/api/client";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AdminHero } from "@/shared/ui/admin-hero";

type PublicationEvent = {
  id: string;
  event_type: string;
  dedupe_key: string;
  status: string;
  attempts: number;
  max_attempts: number;
  claimed_by: string | null;
  last_error: string | null;
  created_at: string;
};

const STATUSES = ["pending", "claimed", "retry", "sent", "dead"] as const;

function statusBadge(status: string) {
  if (status === "pending") return <Badge>pending</Badge>;
  if (status === "claimed") return <Badge variant="secondary">claimed</Badge>;
  if (status === "retry") return <Badge variant="outline">retry</Badge>;
  if (status === "sent") return <Badge variant="outline">sent</Badge>;
  return <Badge variant="destructive">dead</Badge>;
}

export default function PublicationsPage() {
  const [status, setStatus] = React.useState<(typeof STATUSES)[number]>("pending");

  const q = useQuery({
    queryKey: ["publication-events", status],
    queryFn: () =>
      apiGet<PublicationEvent[]>(
        `/api/publication-events?status_filter=${encodeURIComponent(status)}&limit=50`
      ),
    refetchInterval: 3000,
  });

  const rows = q.data || [];
  const retryCount = rows.filter((row) => row.status === "retry").length;

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Publications"
        title="Suivi de la file d'envoi et des events de publication."
        description="Controle l'etat de l'outbox, les retries et les erreurs de delivery sans changer d'ecran."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {rows.length} events
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              filtre {status}
            </div>
            <div className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-4 py-2 text-sm text-fuchsia-100">
              {retryCount} retries
            </div>
          </>
        }
      />

      <Tabs
        value={status}
        onValueChange={(value) => {
          if (STATUSES.includes(value as (typeof STATUSES)[number])) {
            setStatus(value as (typeof STATUSES)[number]);
          }
        }}
      >
        <TabsList>
          {STATUSES.map((item) => (
            <TabsTrigger key={item} value={item}>
              {item}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Visible events</div>
              <CardTitle className="mt-2 text-3xl">{rows.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <BellRing className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Retries</div>
              <CardTitle className="mt-2 text-3xl">{retryCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Clock3 className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Sent</div>
              <CardTitle className="mt-2 text-3xl">
                {rows.filter((row) => row.status === "sent").length}
              </CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <Send className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : q.error ? (
            <div className="text-sm text-destructive">{(q.error as Error).message}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Dedupe</TableHead>
                  <TableHead>Attempts</TableHead>
                  <TableHead>Claimed by</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell>{statusBadge(event.status)}</TableCell>
                    <TableCell className="font-medium">{event.event_type}</TableCell>
                    <TableCell className="font-mono text-xs">{event.dedupe_key}</TableCell>
                    <TableCell className="text-sm">
                      {event.attempts}/{event.max_attempts}
                    </TableCell>
                    <TableCell className="text-sm">{event.claimed_by ?? "-"}</TableCell>
                    <TableCell className="text-sm text-destructive">
                      {event.last_error ?? ""}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
