"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Database, Eye, RefreshCw, Swords } from "lucide-react";
import {
  ingestMatches,
  listMatches,
  getMatchSummary,
} from "@/features/matches/api";
import type { MatchSummary } from "@/features/matches/types";
import { fmtKda } from "@/shared/ui/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

export default function MatchesPage() {
  const [success, setSuccess] = React.useState<string | null>(null);
  const q = useQuery({
    queryKey: ["matches"],
    queryFn: () => listMatches(50),
    refetchInterval: 10000,
  });

  const ingest = useMutation({
    mutationFn: ingestMatches,
    onSuccess: () => {
      setSuccess("Ingestion des matchs terminee.");
      q.refetch();
    },
  });

  const [open, setOpen] = React.useState(false);
  const [summary, setSummary] = React.useState<MatchSummary | null>(null);
  const [summaryErr, setSummaryErr] = React.useState<string | null>(null);

  async function openSummary(riotMatchId: string) {
    setSummary(null);
    setSummaryErr(null);
    setOpen(true);
    try {
      const result = await getMatchSummary(riotMatchId);
      setSummary(result);
    } catch (error) {
      setSummaryErr((error as Error).message);
    }
  }

  const matches = q.data || [];
  const withDuration = matches.filter((match) => match.game_duration !== null).length;

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Matches"
        title="Ingestion et consultation rapide des matchs stockes."
        description="Lance une ingestion manuelle et ouvre un resume detaillé sans quitter la table principale."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {matches.length} matchs charges
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              {withDuration} avec duree
            </div>
          </>
        }
        actions={
          <Button
            onClick={() => ingest.mutate()}
            disabled={ingest.isPending}
            className="justify-between"
          >
            Ingest matches
            <RefreshCw className="h-4 w-4" />
          </Button>
        }
      />

      <MutationStatus
        pending={ingest.isPending}
        success={success}
        error={ingest.error ? (ingest.error as Error).message : null}
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Stored matches</div>
              <CardTitle className="mt-2 text-3xl">{matches.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <Database className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Detailed summaries</div>
              <CardTitle className="mt-2 text-3xl">{withDuration}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Eye className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Recent view</div>
              <CardTitle className="mt-2 text-3xl">50</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <Swords className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Latest matches</CardTitle>
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
                  <TableHead>Match</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Queue</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {matches.map((match) => (
                  <TableRow key={match.riot_match_id}>
                    <TableCell className="font-mono text-xs">
                      {match.riot_match_id}
                    </TableCell>
                    <TableCell>{match.game_mode ?? "-"}</TableCell>
                    <TableCell>{match.queue_id ?? "-"}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {match.game_duration ?? "-"}s
                    </TableCell>
                    <TableCell className="text-xs text-slate-400">
                      {match.created_at}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openSummary(match.riot_match_id)}
                      >
                        Summary
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Match summary</DialogTitle>
          </DialogHeader>

          {!summary && !summaryErr ? <Skeleton className="h-64 w-full" /> : null}
          {summaryErr ? <div className="text-sm text-destructive">{summaryErr}</div> : null}

          {summary ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{summary.riot_match_id}</Badge>
                <Badge variant="outline">{summary.region}</Badge>
                {summary.game_mode ? <Badge>{summary.game_mode}</Badge> : null}
                {summary.queue_id !== null ? (
                  <Badge variant="secondary">queue {summary.queue_id}</Badge>
                ) : null}
                {summary.game_duration !== null ? (
                  <Badge variant="secondary">{summary.game_duration}s</Badge>
                ) : null}
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Player</TableHead>
                    <TableHead>Champ</TableHead>
                    <TableHead>KDA</TableHead>
                    <TableHead>Win</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.participants.slice(0, 10).map((player, index) => (
                    <TableRow key={`${player.puuid}-${index}`}>
                      <TableCell className="text-xs">
                        {player.riot_id_game_name
                          ? `${player.riot_id_game_name}#${player.riot_id_tag_line ?? ""}`
                          : `${player.puuid.slice(0, 10)}...`}
                      </TableCell>
                      <TableCell>{player.champion_name ?? "-"}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {fmtKda(player)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={player.win ? "default" : "secondary"}>
                          {player.win === null ? "?" : player.win ? "win" : "loss"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
