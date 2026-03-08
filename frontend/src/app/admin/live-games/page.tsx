"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Gamepad2, Radar, RefreshCw } from "lucide-react";
import { listLiveGames, refreshLiveGames } from "@/features/live_games/api";
import type { LiveGamePredictionPlayer, LiveGameWinPrediction } from "@/features/live_games/types";
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

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function scoreLabel(player: LiveGamePredictionPlayer): string {
  const score = player.weighted_recent_score;
  return score === null ? "-" : `${score.toFixed(2)}`;
}

function lpLabel(player: LiveGamePredictionPlayer): string {
  return player.elo_lp_total === null ? "-" : String(player.elo_lp_total);
}

function gamesLabel(player: LiveGamePredictionPlayer): string {
  return player.games_count === null ? "N/A" : String(player.games_count);
}

function sourceLabel(player: LiveGamePredictionPlayer): string {
  if (player.history_source === "local") return "local";
  if (player.history_source === "riot") return "riot";
  return "none";
}

function teamRows(prediction: LiveGameWinPrediction, teamId: number): LiveGamePredictionPlayer[] {
  return prediction.players
    .filter((p) => p.team_id === teamId)
    .sort((a, b) => b.skill_value - a.skill_value);
}

function hasSignal(player: LiveGamePredictionPlayer): boolean {
  return player.weighted_recent_score !== null || player.elo_component !== null;
}

function contribution(player: LiveGamePredictionPlayer): string {
  if (!hasSignal(player)) return "Excluded";
  return player.skill_value.toFixed(4);
}

function TeamAnalysisTable({
  teamName,
  teamColor,
  strength,
  winProbability,
  rows,
}: {
  teamName: string;
  teamColor: "blue" | "red";
  strength: number;
  winProbability: number;
  rows: LiveGamePredictionPlayer[];
}) {
  const accent =
    teamColor === "blue"
      ? "border-cyan-300/25 bg-cyan-300/5 text-cyan-100"
      : "border-rose-300/25 bg-rose-300/5 text-rose-100";

  const included = rows.filter((row) => hasSignal(row)).length;
  const excluded = rows.length - included;

  return (
    <div className={`rounded-xl border p-3 md:p-4 ${accent}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold">
          {teamName} | strength {strength.toFixed(4)} | win {pct(winProbability)}
        </div>
        <div className="flex gap-2 text-[11px]">
          <Badge variant="secondary">included {included}</Badge>
          <Badge variant="secondary">excluded {excluded}</Badge>
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Player</TableHead>
            <TableHead>Tracked</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Games</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>ELO</TableHead>
            <TableHead>Signal</TableHead>
            <TableHead>Contribution</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((player) => {
            const signal = hasSignal(player);
            return (
              <TableRow key={player.puuid}>
                <TableCell className="max-w-[180px] truncate font-medium">{player.player_name}</TableCell>
                <TableCell>{player.is_tracked ? "yes" : "no"}</TableCell>
                <TableCell>{sourceLabel(player)}</TableCell>
                <TableCell>{gamesLabel(player)}</TableCell>
                <TableCell>{scoreLabel(player)}</TableCell>
                <TableCell>{lpLabel(player)}</TableCell>
                <TableCell>{signal ? "usable" : "missing"}</TableCell>
                <TableCell className={signal ? "font-mono text-xs" : "text-xs text-slate-400"}>
                  {contribution(player)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

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
  const liveByGame = Array.from(
    rows
      .filter((row) => row.status === "live" && row.game_id)
      .reduce((acc, row) => {
        const gameId = row.game_id as string;
        if (!acc.has(gameId)) {
          acc.set(gameId, []);
        }
        acc.get(gameId)?.push(row);
        return acc;
      }, new Map<string, typeof rows>())
      .entries()
  );

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

      <div className="space-y-4">
        {liveByGame.map(([gameId, gameRows]) => {
          const prediction = gameRows[0]?.win_prediction;
          if (!prediction) return null;
          const blueRows = teamRows(prediction, 100);
          const redRows = teamRows(prediction, 200);

          return (
            <Card key={gameId}>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base">
                  <span>Game {gameId}</span>
                  <span className="text-sm font-medium text-slate-300">
                    Blue {pct(prediction.team_blue.win_probability)} vs Red{" "}
                    {pct(prediction.team_red.win_probability)}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 text-xs text-slate-300 md:grid-cols-4">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <div className="text-[11px] uppercase text-slate-400">Model</div>
                    <div className="mt-1 font-medium">{prediction.model_version}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <div className="text-[11px] uppercase text-slate-400">Blue strength</div>
                    <div className="mt-1 font-medium">{prediction.team_blue.strength.toFixed(4)}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <div className="text-[11px] uppercase text-slate-400">Red strength</div>
                    <div className="mt-1 font-medium">{prediction.team_red.strength.toFixed(4)}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <div className="text-[11px] uppercase text-slate-400">Formula</div>
                    <div className="mt-1 truncate font-medium">{prediction.formula}</div>
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <TeamAnalysisTable
                    teamName="Team Blue"
                    teamColor="blue"
                    strength={prediction.team_blue.strength}
                    winProbability={prediction.team_blue.win_probability}
                    rows={blueRows}
                  />
                  <TeamAnalysisTable
                    teamName="Team Red"
                    teamColor="red"
                    strength={prediction.team_red.strength}
                    winProbability={prediction.team_red.win_probability}
                    rows={redRows}
                  />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
