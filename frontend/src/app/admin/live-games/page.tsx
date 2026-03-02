"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Gamepad2, Radar, RefreshCw } from "lucide-react";
import { listLiveGames, refreshLiveGames } from "@/features/live_games/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { MutationStatus } from "@/shared/ui/mutation-status";

export default function LiveGamesPage() {
  const [success, setSuccess] = React.useState<string | null>(null);

  const q = useQuery({
    queryKey: ["live-games"],
    queryFn: () => listLiveGames(false),
    refetchInterval: 5000,
  });

  const refresh = useMutation({
    mutationFn: refreshLiveGames,
    onSuccess: (result) => {
      setSuccess(
        `Refresh live termine. ${result.updated} updates, ${result.errors} erreurs.`
      );
      q.refetch();
    },
  });

  const rows = q.data || [];
  const liveCount = rows.filter((row) => row.status === "live").length;

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Live games"
        title="Suivi des parties en cours en temps quasi reel."
        description="Controle les etats `live`, relance la collecte et verifie rapidement quel joueur est actuellement en partie."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {rows.length} etats suivis
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              {liveCount} games live
            </div>
          </>
        }
        actions={
          <Button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="justify-between"
          >
            Refresh live games
            <RefreshCw className="h-4 w-4" />
          </Button>
        }
      />

      <MutationStatus
        pending={refresh.isPending}
        success={success}
        error={refresh.error ? (refresh.error as Error).message : null}
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Tracked states</div>
              <CardTitle className="mt-2 text-3xl">{rows.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <Radar className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Live now</div>
              <CardTitle className="mt-2 text-3xl">{liveCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Gamepad2 className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Idle or offline</div>
              <CardTitle className="mt-2 text-3xl">{rows.length - liveCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <RefreshCw className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>States</CardTitle>
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
                  <TableHead>Player</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Game ID</TableHead>
                  <TableHead>Fetched</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.tracked_player_id}>
                    <TableCell>
                      <Badge variant={row.status === "live" ? "default" : "secondary"}>
                        {row.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {row.game_name}#{row.tag_line}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{row.platform ?? "-"}</TableCell>
                    <TableCell className="font-mono text-xs">{row.game_id ?? "-"}</TableCell>
                    <TableCell className="text-xs text-slate-400">{row.fetched_at ?? "-"}</TableCell>
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
