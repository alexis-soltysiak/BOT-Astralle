"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Cog, Play, TimerReset } from "lucide-react";
import { apiGet, apiPost } from "@/features/api/client";
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

type Job = {
  id: string;
  job_key: string;
  description: string;
  interval_seconds: number;
  enabled: boolean;
  last_status: string | null;
  last_error: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
};

export default function JobsPage() {
  const [success, setSuccess] = React.useState<string | null>(null);

  const q = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiGet<Job[]>("/api/jobs"),
    refetchInterval: 5000,
  });

  const runNow = useMutation({
    mutationFn: (jobKey: string) => apiPost(`/api/jobs/${jobKey}/run`, {}),
    onSuccess: (_, jobKey) => {
      setSuccess(`Execution manuelle lancee pour ${jobKey}.`);
      q.refetch();
    },
  });

  const jobs = q.data || [];
  const enabledCount = jobs.filter((job) => job.enabled).length;
  const errorCount = jobs.filter((job) => job.last_status === "error").length;

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Jobs"
        title="Pilotage des workers et execution manuelle des taches."
        description="Surveille les jobs planifies, l'etat des executions et declenche un run manuel lorsque c'est necessaire."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {jobs.length} jobs
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              {enabledCount} actifs
            </div>
            <div className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-4 py-2 text-sm text-fuchsia-100">
              {errorCount} en erreur
            </div>
          </>
        }
      />

      <MutationStatus
        pending={runNow.isPending}
        success={success}
        error={runNow.error ? (runNow.error as Error).message : null}
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Scheduler jobs</div>
              <CardTitle className="mt-2 text-3xl">{jobs.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <Cog className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Enabled</div>
              <CardTitle className="mt-2 text-3xl">{enabledCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <Play className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Errors</div>
              <CardTitle className="mt-2 text-3xl">{errorCount}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <TimerReset className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Jobs list</CardTitle>
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
                  <TableHead>Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Enabled</TableHead>
                  <TableHead>Interval</TableHead>
                  <TableHead>Next run</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>
                      <div className="font-medium">{job.job_key}</div>
                      <div className="text-xs text-slate-400">{job.description}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={job.last_status === "error" ? "destructive" : "outline"}>
                        {job.last_status ?? "n/a"}
                      </Badge>
                      {job.last_error ? (
                        <div className="mt-1 text-xs text-destructive">{job.last_error}</div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Badge variant={job.enabled ? "default" : "secondary"}>
                        {job.enabled ? "enabled" : "disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {job.interval_seconds}s
                    </TableCell>
                    <TableCell className="text-xs text-slate-400">
                      {job.next_run_at ?? "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => runNow.mutate(job.job_key)}
                        disabled={runNow.isPending}
                      >
                        Run now
                      </Button>
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
