"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Database, RefreshCw, Send, Swords } from "lucide-react";
import {
  getMatchSummary,
  ingestMatches,
  listMatches,
  republishMatch,
} from "@/features/matches/api";
import type { MatchParticipant, MatchSummary } from "@/features/matches/types";
import { fmtKda } from "@/shared/ui/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminHero } from "@/shared/ui/admin-hero";
import { MutationStatus } from "@/shared/ui/mutation-status";

const ROLE_ORDER = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT", "UNKNOWN"] as const;

function normalizeRole(participant: MatchParticipant): (typeof ROLE_ORDER)[number] {
  const payload = participant.payload || {};
  const raw = String(payload.teamPosition || payload.individualPosition || "").toUpperCase().trim();
  if (raw === "MIDDLE") return "MID";
  if (raw === "BOTTOM" || raw === "BOT") return "ADC";
  if (raw === "UTILITY") return "SUPPORT";
  if (raw === "TOP" || raw === "JUNGLE" || raw === "MID" || raw === "ADC" || raw === "SUPPORT") return raw;
  return "UNKNOWN";
}

function displayName(player: MatchParticipant) {
  if (player.riot_id_game_name) return `${player.riot_id_game_name}#${player.riot_id_tag_line ?? ""}`;
  return `${player.puuid.slice(0, 10)}...`;
}

function shortMatchId(riotMatchId: string) {
  const idx = riotMatchId.lastIndexOf("_");
  return idx >= 0 ? riotMatchId.slice(idx + 1) : riotMatchId;
}

function formatDuration(seconds: number | null) {
  if (!seconds || seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatDateLabel(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function buildDuels(summary: MatchSummary) {
  const byTeamRole = new Map<string, MatchParticipant>();
  for (const player of summary.participants) {
    const role = normalizeRole(player);
    const team = player.team_id ?? 0;
    byTeamRole.set(`${team}:${role}`, player);
  }
  return ROLE_ORDER.map((role) => ({
    role,
    blue: byTeamRole.get(`100:${role}`) ?? null,
    red: byTeamRole.get(`200:${role}`) ?? null,
  }));
}

function TeamCell({ player, side }: { player: MatchParticipant | null; side: "blue" | "red" }) {
  if (!player) {
    return (
      <div className="rounded-xl border border-dashed border-white/15 bg-white/5 p-3 text-xs text-slate-400">
        no player
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border p-3 ${
        side === "blue" ? "border-cyan-300/25 bg-cyan-500/10" : "border-rose-300/25 bg-rose-500/10"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="truncate text-sm font-semibold text-white">{player.champion_name ?? "Unknown"}</div>
        <Badge variant={player.win ? "default" : "secondary"}>{player.win ? "win" : "loss"}</Badge>
      </div>
      <div className="mt-1 truncate text-xs text-slate-300">{displayName(player)}</div>
      <div className="mt-2 text-xs font-mono text-slate-200">{fmtKda(player)}</div>
    </div>
  );
}

export default function MatchesPage() {
  const [success, setSuccess] = React.useState<string | null>(null);
  const [expandedMatchId, setExpandedMatchId] = React.useState<string | null>(null);
  const [summaryByMatch, setSummaryByMatch] = React.useState<Record<string, MatchSummary>>({});
  const [summaryErrByMatch, setSummaryErrByMatch] = React.useState<Record<string, string>>({});
  const [loadingSummaryId, setLoadingSummaryId] = React.useState<string | null>(null);
  const [republishingId, setRepublishingId] = React.useState<string | null>(null);

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

  const republish = useMutation({
    mutationFn: republishMatch,
    onSuccess: (result) => {
      setSuccess(`Republication queuee pour ${result.riot_match_id}.`);
    },
  });

  const matches = q.data || [];
  const withDuration = matches.filter((match) => match.game_duration !== null).length;

  async function handleExpandMatch(riotMatchId: string) {
    if (expandedMatchId === riotMatchId) {
      setExpandedMatchId(null);
      return;
    }
    setExpandedMatchId(riotMatchId);
    if (summaryByMatch[riotMatchId] || loadingSummaryId === riotMatchId) return;

    setLoadingSummaryId(riotMatchId);
    setSummaryErrByMatch((prev) => ({ ...prev, [riotMatchId]: "" }));
    try {
      const summary = await getMatchSummary(riotMatchId);
      setSummaryByMatch((prev) => ({ ...prev, [riotMatchId]: summary }));
    } catch (error) {
      setSummaryErrByMatch((prev) => ({ ...prev, [riotMatchId]: (error as Error).message }));
    } finally {
      setLoadingSummaryId(null);
    }
  }

  async function handleRepublish(riotMatchId: string) {
    setRepublishingId(riotMatchId);
    try {
      await republish.mutateAsync(riotMatchId);
    } finally {
      setRepublishingId(null);
    }
  }

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Matches"
        title="Ingestion et republication Discord des matchs."
        description="Chaque ligne expose un duel clair par lane et permet de republier instantanement l'embed."
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
        pending={ingest.isPending || republish.isPending}
        success={success}
        error={
          ingest.error
            ? (ingest.error as Error).message
            : republish.error
              ? (republish.error as Error).message
              : null
        }
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
              <div className="text-sm text-slate-400">Matchups loaded</div>
              <CardTitle className="mt-2 text-3xl">{Object.keys(summaryByMatch).length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Swords className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Ready to republish</div>
              <CardTitle className="mt-2 text-3xl">{matches.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <Send className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <div className="space-y-4">
        {q.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : q.error ? (
          <div className="text-sm text-destructive">{(q.error as Error).message}</div>
        ) : (
          matches.map((match) => {
            const isExpanded = expandedMatchId === match.riot_match_id;
            const summary = summaryByMatch[match.riot_match_id];
            const duels = summary ? buildDuels(summary) : [];
            const blueWon = summary?.participants.some((p) => p.team_id === 100 && p.win);
            const redWon = summary?.participants.some((p) => p.team_id === 200 && p.win);

            return (
              <Card key={match.riot_match_id} className="overflow-hidden border-white/10 bg-slate-950/40">
                <CardContent className="space-y-4 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {match.riot_match_id}
                        </Badge>
                        <Badge variant="secondary">#{shortMatchId(match.riot_match_id)}</Badge>
                        {match.game_mode ? <Badge>{match.game_mode}</Badge> : null}
                        {match.queue_id !== null ? <Badge variant="outline">queue {match.queue_id}</Badge> : null}
                        <Badge variant="outline">{formatDuration(match.game_duration)}</Badge>
                      </div>
                      <div className="text-xs text-slate-400">{formatDateLabel(match.created_at)}</div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant={isExpanded ? "secondary" : "outline"}
                        onClick={() => handleExpandMatch(match.riot_match_id)}
                        disabled={loadingSummaryId === match.riot_match_id}
                      >
                        <Swords className="mr-2 h-4 w-4" />
                        {isExpanded ? "Masquer le matchup" : "Voir le matchup"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleRepublish(match.riot_match_id)}
                        disabled={republishingId === match.riot_match_id}
                      >
                        <Send className="mr-2 h-4 w-4" />
                        {republishingId === match.riot_match_id ? "Envoi..." : "Republier Discord"}
                      </Button>
                    </div>
                  </div>

                  {isExpanded ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                      {loadingSummaryId === match.riot_match_id ? <Skeleton className="h-48 w-full" /> : null}
                      {summaryErrByMatch[match.riot_match_id] ? (
                        <div className="text-sm text-destructive">{summaryErrByMatch[match.riot_match_id]}</div>
                      ) : null}

                      {summary ? (
                        <div className="space-y-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/20">
                              Blue {blueWon ? "winner" : "team"}
                            </Badge>
                            <Badge className="bg-rose-500/20 text-rose-100 hover:bg-rose-500/20">
                              Red {redWon ? "winner" : "team"}
                            </Badge>
                            {summary.game_duration !== null ? (
                              <Badge variant="outline">{formatDuration(summary.game_duration)}</Badge>
                            ) : null}
                          </div>

                          <div className="space-y-3">
                            {duels.map((duel) => (
                              <div
                                key={`${summary.riot_match_id}-${duel.role}`}
                                className="grid items-center gap-3 rounded-xl border border-white/10 bg-slate-950/70 p-3 md:grid-cols-[1fr_auto_1fr]"
                              >
                                <TeamCell player={duel.blue} side="blue" />
                                <div className="flex items-center justify-center">
                                  <Badge variant="outline" className="min-w-20 justify-center">
                                    {duel.role}
                                  </Badge>
                                </div>
                                <TeamCell player={duel.red} side="red" />
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
