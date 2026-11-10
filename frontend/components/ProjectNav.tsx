"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, rememberProject, type Project } from "@/lib/api";

/** Header + step tabs shared by every project page. */
export default function ProjectNav({ projectId }: { projectId: number }) {
  const path = usePathname();
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    rememberProject(projectId);
    api.getProject(projectId).then(setProject).catch(() => setProject(null));
  }, [projectId]);

  const tabs = [
    { href: "/", label: "1–3 Drawings", match: (p: string) => p === "/" || p.startsWith("/drawings") },
    { href: `/projects/${projectId}/quantities`, label: "4 Quantities", match: (p: string) => p.endsWith("/quantities") },
    { href: `/projects/${projectId}/catalog`, label: "5 Contract catalog", match: (p: string) => p.endsWith("/catalog") },
    { href: `/projects/${projectId}/estimaciones`, label: "6 Estimación check", match: (p: string) => p.endsWith("/estimaciones") },
    { href: `/projects/${projectId}/field`, label: "Field progress", match: (p: string) => p.endsWith("/field") },
    { href: `/projects/${projectId}/reports`, label: "Reports & bids", match: (p: string) => p.endsWith("/reports") },
    { href: `/projects/${projectId}/details`, label: "Project details", match: (p: string) => p.endsWith("/details") },
  ];

  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link href="/" className="text-2xl font-semibold">
          INPROS Estimations
        </Link>
        <span className="text-sm text-slate-500">{project ? project.name : ""}</span>
      </div>
      <nav className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {tabs.map((t) => {
          const active = t.match(path);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
                active ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
        <span className="ml-auto self-center whitespace-nowrap px-2 text-xs text-slate-400">Revision changes: open a drawing with 2+ versions</span>
      </nav>
    </div>
  );
}
