export function formatRank(state: {
  tier: string | null;
  division: string | null;
  league_points: number | null;
}) {
  if (!state.tier) return "Unranked";
  const div = state.division ? ` ${state.division}` : "";
  const lp = state.league_points !== null && state.league_points !== undefined ? ` — ${state.league_points} LP` : "";
  return `${state.tier}${div}${lp}`;
}

export function fmtKda(p: { kills: number | null; deaths: number | null; assists: number | null }) {
  if (p.kills === null || p.deaths === null || p.assists === null) return "-";
  return `${p.kills}/${p.deaths}/${p.assists}`;
}