"use client";

import Link from "next/link";

const items = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/tracked-players", label: "Tracked Players" },
  { href: "/admin/leaderboards", label: "Leaderboards" },
  { href: "/admin/live-games", label: "Live Games" },
  { href: "/admin/matches", label: "Matches" },
  { href: "/admin/publications", label: "Publications" },
  { href: "/admin/jobs", label: "Jobs" },
];

export default function Nav() {
  return (
    <nav style={{ width: 240, padding: 24, borderRight: "1px solid #eee" }}>
      <div style={{ fontWeight: 700, marginBottom: 16 }}>Astralle Admin</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items.map((i) => (
          <Link key={i.href} href={i.href} style={{ textDecoration: "none" }}>
            {i.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}