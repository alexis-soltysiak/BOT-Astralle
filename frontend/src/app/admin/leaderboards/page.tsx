"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, RefreshCw, Trophy } from "lucide-react";
import { getLeaderboards, refreshLeaderboards } from "@/features/leaderboards/api";
import type { LeaderboardRow } from "@/features/leaderboards/types";
import { formatRank } from "@/shared/ui/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

export default function LeaderboardsPage() {
  const [sort, setSort] = React.useState<"solo" | "flex">("solo");
  const [success, setSuccess] = React.useState<string | null>(null);

  const q = useQuery({
    queryKey: ["leaderboards", sort],
    queryFn: () => getLeaderboards(sort),
    refetchInterval: 10000,
  });

  const refresh = useMutation({
    mutationFn: refreshLeaderboards,
    onSuccess: (result) => {
      setSuccess(
        `Refresh termine. ${result.created} snapshots crees, ${result.skipped} ignores.`
      );
      q.refetch();
    },
  });

  const rows = q.data || [];
  const fetchedRows = rows.filter((row) =>
    Boolean(sort === "solo" ? row.solo.fetched_at : row.flex.fetched_at)
  ).length;

  function rowRank(row: LeaderboardRow) {
    return sort === "solo" ? formatRank(row.solo) : formatRank(row.flex);
  }

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Leaderboards"
        title="Snapshots SoloQ et Flex avec refresh immediat."
        description="Visualise rapidement l'etat des classements importes et relance la collecte sans quitter la page."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {rows.length} lignes visibles
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              {fetchedRows} snapshots horodates
            </div>
            <div className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-4 py-2 text-sm text-fuchsia-100">
              Vue {sort.toUpperCase()}
            </div>
          </>
        }
        actions={
          <Button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="justify-between"
          >
            Refresh leaderboards
            <RefreshCw className="h-4 w-4" />
          </Button>
        }
      />

      <MutationStatus
        pending={refresh.isPending}
        success={success}
        error={refresh.error ? (refresh.error as Error).message : null}
      />

      <section className="flex flex-wrap items-center gap-4">
        <Tabs
          value={sort}
          onValueChange={(value) => {
            if (value === "solo" || value === "flex") {
              setSort(value);
            }
          }}
        >
          <TabsList>
            <TabsTrigger value="solo">SoloQ</TabsTrigger>
            <TabsTrigger value="flex">Flex</TabsTrigger>
          </TabsList>
        </Tabs>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Current board</div>
              <CardTitle className="mt-2 text-3xl">{sort.toUpperCase()}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <BarChart3 className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Players ranked</div>
              <CardTitle className="mt-2 text-3xl">{rows.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Trophy className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Snapshots fetched</div>
              <CardTitle className="mt-2 text-3xl">{fetchedRows}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <RefreshCw className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{sort === "solo" ? "SoloQ" : "Flex"} leaderboard</CardTitle>
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
                  <TableHead>#</TableHead>
                  <TableHead>Player</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Rank</TableHead>
                  <TableHead>W/L</TableHead>
                  <TableHead>Fetched</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => {
                  const state = sort === "solo" ? row.solo : row.flex;
                  const wl =
                    state.wins === null || state.losses === null
                      ? "-"
                      : `${state.wins}/${state.losses}`;

                  return (
                    <TableRow key={row.tracked_player_id}>
                      <TableCell className="font-mono text-xs">{index + 1}</TableCell>
                      <TableCell className="font-medium">
                        {row.game_name}#{row.tag_line}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{row.platform ?? "-"}</TableCell>
                      <TableCell>
                        <Badge variant={state.tier ? "default" : "secondary"}>
                          {rowRank(row)}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{wl}</TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {state.fetched_at ?? "-"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
