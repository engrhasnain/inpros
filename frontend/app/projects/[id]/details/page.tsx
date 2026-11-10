"use client";

import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Button, Card, Chip, ErrorNote, useAsync } from "@/components/ui";
import { api, type Project, type ProjectDetails, type Readiness } from "@/lib/api";

const FIELDS: { key: keyof ProjectDetails; label: string; placeholder: string; wide?: boolean; multiline?: boolean }[] = [
  { key: "name", label: "Project name", placeholder: "Oficinas Ejército Nacional – 3er nivel", wide: true },
  { key: "client", label: "Client", placeholder: "INPROS" },
  { key: "contract_number", label: "Contract number", placeholder: "INP-2026-014" },
  { key: "contractor", label: "Contractor", placeholder: "Company that executes the work" },
  { key: "location", label: "Location", placeholder: "Address" },
  { key: "scope", label: "Scope of work", placeholder: "What the contract covers", wide: true, multiline: true },
  { key: "supervisor_name", label: "Prepared by — name", placeholder: "Ing. …" },
  { key: "supervisor_title", label: "Prepared by — title", placeholder: "Supervisor de obra" },
  { key: "approver_name", label: "Approved by — name", placeholder: "Lic. …" },
  { key: "approver_title", label: "Approved by — title", placeholder: "Director de Administración" },
];

function DetailsPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [form, setForm] = useState<ProjectDetails>({});
  const [ready, setReady] = useState<Readiness | null>(null);
  const [saved, setSaved] = useState(false);
  const { busy, error, run } = useAsync();

  useEffect(() => {
    run(async () => {
      const [p, r] = await Promise.all([api.getProject(projectId), api.readiness(projectId)]);
      setForm(pick(p));
      setReady(r);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per project
  }, [projectId]);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const p = await api.updateProject(projectId, form);
      setForm(pick(p));
      setReady(await api.readiness(projectId));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    });
  };

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />
      <Card
        title="Project details used in every report"
        actions={ready && (ready.ready ? <Chip tone="green">Ready for reports</Chip> : <Chip tone="amber">Reports blocked: details missing</Chip>)}
      >
        <p className="px-4 pt-3 text-sm text-slate-600">
          Enter these once. Every dictamen, bid evaluation and progress report takes the contract number, scope and
          signatories from here — nothing is copied and pasted, so they are always the same.
        </p>
        {ready && !ready.ready && (
          <ul className="mx-4 mt-3 list-disc rounded-lg bg-amber-50 py-2 pl-8 pr-3 text-sm text-amber-900">
            {ready.missing.map((m) => <li key={m}>Missing: {m}</li>)}
            {ready.problems.map((m) => <li key={m}>{m}</li>)}
          </ul>
        )}
        <form onSubmit={save} className="grid gap-4 p-4 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <label key={f.key} className={f.wide ? "sm:col-span-2" : ""}>
              <span className="text-xs font-medium text-slate-500">{f.label}</span>
              {f.multiline ? (
                <textarea rows={3} value={(form[f.key] as string) ?? ""} placeholder={f.placeholder}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              ) : (
                <input value={(form[f.key] as string) ?? ""} placeholder={f.placeholder}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              )}
            </label>
          ))}
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : "Save details"}</Button>
            {saved && <span className="text-sm text-green-700">Saved</span>}
          </div>
        </form>
      </Card>
    </main>
  );
}

function pick(p: Project): ProjectDetails {
  const out: ProjectDetails = {};
  for (const f of FIELDS) (out as Record<string, unknown>)[f.key] = p[f.key as keyof Project] ?? "";
  return out;
}

export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <DetailsPage />
    </Suspense>
  );
}
