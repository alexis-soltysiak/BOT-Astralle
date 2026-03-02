"use client";

import React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Copy, Plus, RefreshCw, ShieldCheck, Users } from "lucide-react";
import {
  listTrackedPlayers,
  createTrackedPlayer,
  patchTrackedPlayer,
} from "@/features/tracked_players/api";
import type { TrackedPlayerCreate } from "@/features/tracked_players/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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

const defaultForm: TrackedPlayerCreate = {
  discord_user_id: "",
  discord_display_name: "",
  game_name: "",
  tag_line: "",
  region: "europe",
  platform: "euw1",
  active: true,
};

function PuuidCell({ puuid }: { puuid: string | null }) {
  const [copied, setCopied] = React.useState(false);

  if (!puuid) {
    return <span>-</span>;
  }

  const resolvedPuuid = puuid;
  const short = `${resolvedPuuid.slice(0, 10)}...`;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(resolvedPuuid);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="group relative inline-flex items-center">
      <button
        type="button"
        onClick={handleCopy}
        className="rounded-md px-2 py-1 text-left font-mono text-xs text-slate-200 transition hover:bg-white/5"
        title={resolvedPuuid}
      >
        {short}
      </button>
      <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-[28rem] max-w-[70vw] rounded-xl border border-cyan-300/20 bg-slate-950/95 p-3 opacity-0 shadow-2xl shadow-cyan-950/40 transition duration-150 group-hover:pointer-events-auto group-hover:opacity-100">
        <div className="mb-2 text-[11px] uppercase tracking-[0.22em] text-slate-400">
          PUUID complet
        </div>
        <div className="flex items-start gap-2">
          <textarea
            readOnly
            value={resolvedPuuid}
            rows={2}
            className="min-h-[3.5rem] flex-1 resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-slate-100 outline-none"
            onFocus={(event) => event.currentTarget.select()}
          />
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="shrink-0"
            onClick={handleCopy}
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copie" : "Copier"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function TrackedPlayersPage() {
  const q = useQuery({
    queryKey: ["tracked-players"],
    queryFn: listTrackedPlayers,
    refetchInterval: 5000,
  });

  const players = q.data || [];
  const [statusMessage, setStatusMessage] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState<TrackedPlayerCreate>(defaultForm);

  const create = useMutation({
    mutationFn: () => createTrackedPlayer(form),
    onSuccess: () => {
      setOpen(false);
      setForm(defaultForm);
      setStatusMessage("Tracked player cree et synchronise.");
      q.refetch();
    },
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      patchTrackedPlayer(id, { active }),
    onSuccess: (_, variables) => {
      setStatusMessage(
        variables.active ? "Player reactive." : "Player desactive."
      );
      q.refetch();
    },
  });

  const setPlatform = useMutation({
    mutationFn: ({ id, platform }: { id: string; platform: string }) =>
      patchTrackedPlayer(id, { platform }),
    onSuccess: (_, variables) => {
      setStatusMessage(`Plateforme mise a jour sur ${variables.platform}.`);
      q.refetch();
    },
  });

  const refreshing = q.isRefetching || q.isLoading;
  const activePlayers = players.filter((player) => player.active).length;
  const resolvedPlayers = players.filter((player) => Boolean(player.puuid)).length;

  return (
    <div className="space-y-6 md:space-y-8">
      <AdminHero
        eyebrow="Tracked players"
        title="Gestion des joueurs suivis et des identites Riot."
        description="Ajoute, active ou reconfigure les comptes surveilles par le backend. Toutes les actions importantes affichent un retour visible."
        metrics={
          <>
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {players.length} profils suivis
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              {activePlayers} actifs
            </div>
            <div className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-4 py-2 text-sm text-fuchsia-100">
              {resolvedPlayers} PUUID resolus
            </div>
          </>
        }
        actions={
          <>
            <Button onClick={() => q.refetch()} disabled={refreshing} className="justify-between">
              Rafraichir la liste
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button variant="secondary" className="justify-between">
                  Ajouter un joueur
                  <Plus className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Ajouter un tracked player</DialogTitle>
                </DialogHeader>

                <div className="grid gap-4">
                  <div className="grid gap-2 md:grid-cols-2">
                    <Input
                      placeholder="discord_user_id"
                      value={form.discord_user_id}
                      onChange={(e) =>
                        setForm({ ...form, discord_user_id: e.target.value })
                      }
                    />
                    <Input
                      placeholder="discord_display_name"
                      value={form.discord_display_name ?? ""}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          discord_display_name: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div className="grid gap-2 md:grid-cols-2">
                    <Input
                      placeholder="game_name"
                      value={form.game_name}
                      onChange={(e) =>
                        setForm({ ...form, game_name: e.target.value })
                      }
                    />
                    <Input
                      placeholder="tag_line"
                      value={form.tag_line}
                      onChange={(e) =>
                        setForm({ ...form, tag_line: e.target.value })
                      }
                    />
                  </div>

                  <div className="grid gap-2 md:grid-cols-2">
                    <Input
                      placeholder="region"
                      value={form.region}
                      onChange={(e) =>
                        setForm({ ...form, region: e.target.value })
                      }
                    />
                    <Input
                      placeholder="platform"
                      value={form.platform ?? ""}
                      onChange={(e) =>
                        setForm({ ...form, platform: e.target.value })
                      }
                    />
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm leading-6 text-slate-300">
                    Le backend tente de resoudre automatiquement le PUUID. Cela
                    necessite une variable `RIOT_API_KEY` valide cote backend.
                  </div>

                  <MutationStatus
                    pending={create.isPending}
                    error={create.error ? (create.error as Error).message : null}
                  />

                  <div className="flex justify-end">
                    <Button onClick={() => create.mutate()} disabled={create.isPending}>
                      Creer le joueur
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </>
        }
      />

      <MutationStatus
        pending={toggleActive.isPending || setPlatform.isPending}
        success={statusMessage}
        error={
          (toggleActive.error as Error | null)?.message ??
          (setPlatform.error as Error | null)?.message ??
          null
        }
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Total players</div>
              <CardTitle className="mt-2 text-3xl">{players.length}</CardTitle>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-200">
              <Users className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Active tracking</div>
              <CardTitle className="mt-2 text-3xl">{activePlayers}</CardTitle>
            </div>
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="text-sm text-slate-400">Resolved PUUID</div>
              <CardTitle className="mt-2 text-3xl">{resolvedPlayers}</CardTitle>
            </div>
            <div className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-3 text-fuchsia-200">
              <RefreshCw className="h-5 w-5" />
            </div>
          </CardHeader>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Players</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : q.error ? (
            <div className="text-sm text-destructive">
              {(q.error as Error).message}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Discord</TableHead>
                  <TableHead>Player</TableHead>
                  <TableHead>Region</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>PUUID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {players.map((player) => (
                  <TableRow key={player.id}>
                    <TableCell className="font-medium">
                      <div>{player.discord_display_name ?? "-"}</div>
                      <div className="font-mono text-xs text-slate-400">
                        {player.discord_user_id ?? "-"}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">
                      {player.game_name}#{player.tag_line}
                    </TableCell>
                    <TableCell>{player.region}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {player.platform ?? "-"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <PuuidCell puuid={player.puuid} />
                    </TableCell>
                    <TableCell>
                      <Badge variant={player.active ? "default" : "secondary"}>
                        {player.active ? "active" : "disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            toggleActive.mutate({
                              id: player.id,
                              active: !player.active,
                            })
                          }
                          disabled={toggleActive.isPending}
                        >
                          {player.active ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            setPlatform.mutate({ id: player.id, platform: "euw1" })
                          }
                          disabled={setPlatform.isPending}
                        >
                          Set EUW1
                        </Button>
                      </div>
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
