"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Database,
  Radar,
  Sparkles,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/features/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

type Job = {
  job_key: string;
  enabled: boolean;
  last_status: string | null;
  next_run_at: string | null;
};
type PublicationEvent = { id: string; status: string };
type Match = { riot_match_id: string };

function formatDate(value: string | null) {
  if (!value) {
    return "Not scheduled";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export default function AdminDashboard() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiGet<Job[]>("/api/jobs"),
    refetchInterval: 5000,
  });
  const pending = useQuery({
    queryKey: ["pubs-pending"],
    queryFn: () =>
      apiGet<PublicationEvent[]>(
        "/api/publication-events?status_filter=pending&limit=50"
      ),
    refetchInterval: 3000,
  });
  const matches = useQuery({
    queryKey: ["matches"],
    queryFn: () => apiGet<Match[]>("/api/matches?limit=5"),
    refetchInterval: 5000,
  });

  const refreshLb = useMutation({
    mutationFn: () => apiPost("/api/leaderboards/refresh", {}),
    onSuccess: () => jobs.refetch(),
  });

  const refreshLive = useMutation({
    mutationFn: () => apiPost("/api/live-games/refresh", {}),
    onSuccess: () => jobs.refetch(),
  });

  const ingestMatches = useMutation({
    mutationFn: () => apiPost("/api/matches/ingest", {}),
    onSuccess: () => {
      pending.refetch();
      matches.refetch();
    },
  });

  const jobsData = jobs.data || [];
  const matchesData = matches.data || [];
  const pendingCount = pending.data?.length ?? 0;
  const activeJobs = jobsData.filter((job) => job.enabled).length;
  const failedJobs = jobsData.filter((job) => job.last_status === "error").length;
  const latestScheduledJob = jobsData.find((job) => job.next_run_at);

  return (
    <div className="space-y-6 md:space-y-8">
      <section className="glass-panel aurora-border relative overflow-hidden rounded-[32px] p-6 md:p-8">
        <div className="absolute inset-y-0 right-0 hidden w-1/2 bg-[radial-gradient(circle_at_center,rgba(110,231,255,0.18),transparent_58%)] md:block" />
        <div className="relative flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <Badge className="mb-4">Astralle control room</Badge>
            <h1 className="max-w-2xl text-4xl font-semibold text-white md:text-5xl">
              Dashboard d&apos;administration premium, aligne sur l&apos;univers du logo.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
              Supervision des jobs, ingestion des matchs, publications en attente
              et sante globale de la plateforme dans une interface plus nette et
              plus professionnelle.
            </p>

            <div className="mt-6 flex flex-wrap gap-3 text-sm text-slate-200">
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2">
                <Sparkles className="h-4 w-4 text-cyan-300" />
                Couleurs inspirees du logo
              </div>
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2">
                <Radar className="h-4 w-4 text-fuchsia-300" />
                Monitoring temps reel
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:w-[430px] xl:grid-cols-1">
            <Button
              onClick={() => refreshLb.mutate()}
              disabled={refreshLb.isPending}
              className="justify-between"
            >
              Refresh Leaderboards
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => refreshLive.mutate()}
              disabled={refreshLive.isPending}
              variant="secondary"
              className="justify-between"
            >
              Refresh Live
              <Zap className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => ingestMatches.mutate()}
              disabled={ingestMatches.isPending}
              variant="outline"
              className="justify-between"
            >
              Ingest Matches
              <Database className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Pending publications</div>
              <CardTitle className="mt-2 text-3xl">{pendingCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Activity className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            {pending.isLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : pending.error ? (
              <div className="text-sm text-destructive">
                {(pending.error as Error).message}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-300">
                Elements en attente de diffusion vers Discord et les autres sorties
                automatiques.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Jobs actifs</div>
              <CardTitle className="mt-2 text-3xl">{activeJobs}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <Radar className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            {jobs.isLoading ? (
              <Skeleton className="h-6 w-40" />
            ) : jobs.error ? (
              <div className="text-sm text-destructive">
                {(jobs.error as Error).message}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-300">
                {failedJobs > 0
                  ? `${failedJobs} job(s) sont actuellement en erreur.`
                  : "Aucune erreur detectee sur les workers visibles."}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Latest matches</div>
              <CardTitle className="mt-2 text-3xl">{matchesData.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-sky-300/20 bg-sky-300/10 p-3 text-sky-200">
              <Database className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            {matches.isLoading ? (
              <Skeleton className="h-6 w-32" />
            ) : matches.error ? (
              <div className="text-sm text-destructive">
                {(matches.error as Error).message}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-300">
                Derniere fenetre d&apos;ingestion disponible pour controle rapide des
                identifiants Riot.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Next run</div>
              <CardTitle className="mt-2 text-lg">
                {formatDate(latestScheduledJob?.next_run_at ?? null)}
              </CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-white">
              <Zap className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-6 text-slate-300">
              {latestScheduledJob?.job_key ??
                "Aucune planification disponible pour le moment."}
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <div className="text-sm text-slate-400">Job health</div>
              <CardTitle className="mt-2">Workers et planification</CardTitle>
            </div>
            <Badge variant="outline">Live</Badge>
          </CardHeader>
          <CardContent>
            {jobs.isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : jobs.error ? (
              <div className="text-sm text-destructive">
                {(jobs.error as Error).message}
              </div>
            ) : (
              <div className="space-y-3">
                {jobsData.slice(0, 6).map((j) => (
                  <div
                    key={j.job_key}
                    className="flex flex-col gap-3 rounded-2xl border border-white/[0.08] bg-black/10 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <div className="font-medium text-white">{j.job_key}</div>
                      <div className="mt-1 text-sm text-slate-400">
                        Next run: {formatDate(j.next_run_at)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={j.enabled ? "default" : "secondary"}>
                        {j.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                      <Badge
                        variant={
                          j.last_status === "error" ? "destructive" : "outline"
                        }
                      >
                        {j.last_status ?? "Unknown"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="text-sm text-slate-400">Recent matches</div>
            <CardTitle className="mt-2">Derniers identifiants collectes</CardTitle>
          </CardHeader>
          <CardContent>
            {matches.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : matches.error ? (
              <div className="text-sm text-destructive">
                {(matches.error as Error).message}
              </div>
            ) : (
              <div className="space-y-3">
                {matchesData.map((m, index) => (
                  <div
                    key={m.riot_match_id}
                    className="rounded-2xl border border-white/[0.08] bg-black/10 p-4"
                  >
                    <div className="text-xs uppercase tracking-[0.22em] text-slate-500">
                      Match {index + 1}
                    </div>
                    <div className="mt-2 font-mono text-xs text-cyan-100 md:text-sm">
                      {m.riot_match_id}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
