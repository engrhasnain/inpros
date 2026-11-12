"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, lastProject, rememberProject, type Drawing, type Project } from "@/lib/api";

const ACCEPTED = [".dwg", ".dxf"];
const isDrawingFile = (f: File) => ACCEPTED.some((ext) => f.name.toLowerCase().endsWith(ext));

type UploadRow = {
  key: string;
  name: string;
  state: "waiting" | "working" | "done" | "duplicate" | "failed";
  message?: string;
};

const NEXT_STEPS = [
  { title: "Quantities", text: "Fixtures counted and conduit / trays measured, per sheet", path: "quantities" },
  { title: "Contract catalog", text: "Upload the catálogo de conceptos and link each line to the drawings", path: "catalog" },
  { title: "Estimación check", text: "Check the contractor's claim against contract, approvals and drawings", path: "estimaciones" },
  { title: "Revision changes", text: "Upload a new version of a drawing, then open it to see what changed and the cost", path: null },
];

export default function Home() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [backendMsg, setBackendMsg] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [busy, setBusy] = useState(false);

  const refreshDrawings = useCallback(async (p: Project) => {
    setDrawings(await api.listDrawings(p.id).catch(() => []));
  }, []);

  const selectProject = useCallback(
    (p: Project) => {
      setProject(p);
      rememberProject(p.id);
      setUploads([]);
      setDrawings([]);
      refreshDrawings(p);
    },
    [refreshDrawings],
  );

  useEffect(() => {
    api
      .health()
      .then(() => {
        setBackendOk(true);
        setBackendMsg("Backend connected");
        return api.listProjects();
      })
      .then((list) => {
        setProjects(list);
        const last = lastProject();
        const pick = list.find((p) => p.id === last) ?? list[0];
        if (pick) selectProject(pick);
      })
      .catch((e: Error) => {
        setBackendOk(false);
        setBackendMsg(e.message);
      });
  }, [selectProject]);

  async function handleFiles(files: File[]) {
    if (!project || busy) return;
    const dwgs = files.filter(isDrawingFile);
    const skipped = files.filter((f) => !isDrawingFile(f));
    const rows: UploadRow[] = [
      ...dwgs.map((f, i) => ({ key: `${Date.now()}-${i}`, name: f.name, state: "waiting" as const })),
      ...skipped.map((f, i) => ({
        key: `skip-${Date.now()}-${i}`,
        name: f.name,
        state: "failed" as const,
        message: "Not a .dwg or .dxf file, skipped",
      })),
    ];
    setUploads(rows);
    setBusy(true);

    // One at a time: each drawing takes a second or two to read.
    for (let i = 0; i < dwgs.length; i++) {
      const key = rows[i].key;
      const update = (patch: Partial<UploadRow>) =>
        setUploads((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
      update({ state: "working" });
      try {
        const res = await api.uploadDrawing(project.id, dwgs[i]);
        if (res.duplicate) {
          update({ state: "duplicate", message: `Same file as version ${res.version.version}, nothing changed` });
        } else if (res.version.status === "ready") {
          update({
            state: "done",
            message: `Version ${res.version.version} · ${res.version.object_count?.toLocaleString()} objects · ${res.version.symbol_count?.toLocaleString()} symbols`,
          });
        } else {
          update({ state: "failed", message: res.version.error ?? "Could not read this drawing" });
        }
      } catch (e) {
        update({ state: "failed", message: (e as Error).message });
      }
      await refreshDrawings(project);
    }
    setBusy(false);
  }

  async function removeProject(p: Project) {
    if (!window.confirm(`Delete the project "${p.name}" and everything in it (drawings, catalog, estimaciones, bids, site progress)?\n\nThis cannot be undone.`)) return;
    try {
      await api.deleteProject(p.id);
      const rest = projects.filter((x) => x.id !== p.id);
      setProjects(rest);
      if (rest.length) selectProject(rest[0]);
      else {
        setProject(null);
        setDrawings([]);
        setUploads([]);
      }
    } catch (e) {
      window.alert((e as Error).message);
    }
  }

  async function removeDrawing(d: Drawing) {
    if (!project) return;
    if (!window.confirm(`Delete the drawing "${d.name}" with all its versions?\n\nThis cannot be undone.`)) return;
    try {
      await api.deleteDrawing(d.id);
      await refreshDrawings(project);
    } catch (e) {
      window.alert((e as Error).message);
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">INPROS Estimations</h1>
          <p className="text-sm text-slate-500">Upload project drawings → get quantities → validate estimaciones</p>
        </div>
        <StatusPill ok={backendOk} text={backendOk === null ? "Connecting…" : backendMsg} />
      </header>

      <div className="space-y-6">
        <Step n={1} title="Choose a project">
          <ProjectPicker
            projects={projects}
            current={project}
            onSelect={selectProject}
            onCreated={(p) => {
              setProjects((prev) => [p, ...prev]);
              selectProject(p);
            }}
            onDelete={removeProject}
            disabled={backendOk === false && projects.length === 0 && backendMsg.startsWith("Cannot")}
          />
        </Step>

        <Step n={2} title="Upload drawings" muted={!project}>
          {project ? (
            <>
              <DropZone onFiles={handleFiles} busy={busy} />
              {uploads.length > 0 && (
                <ul className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                  {uploads.map((u) => (
                    <li key={u.key} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                      <UploadIcon state={u.state} />
                      <span className="min-w-0 flex-1 truncate font-medium">{u.name}</span>
                      <span className="text-right text-slate-500">
                        {u.state === "waiting" ? "Waiting…" : u.state === "working" ? "Reading drawing…" : u.message}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">Create or choose a project first.</p>
          )}
        </Step>

        <Step n={3} title="Drawings in this project" muted={!project}>
          {drawings.length === 0 ? (
            <p className="text-sm text-slate-500">No drawings yet.</p>
          ) : (
            <DrawingsTable drawings={drawings} onDelete={removeDrawing} />
          )}
        </Step>

        <section>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">Next steps</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {NEXT_STEPS.map((s, i) => {
              const body = (
                <>
                  <div className="text-sm font-semibold">
                    {i + 4}. {s.title} {s.path && project && <span className="text-blue-600">→</span>}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{s.text}</div>
                </>
              );
              return s.path && project && drawings.length > 0 ? (
                <Link key={s.title} href={`/projects/${project.id}/${s.path}`} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-400 hover:shadow">
                  {body}
                </Link>
              ) : (
                <div key={s.title} className={`rounded-xl border p-4 ${s.path ? "border-dashed border-slate-300 opacity-60" : "border-slate-200 bg-white"}`}>
                  {body}
                  {s.path && <div className="mt-2 text-xs text-slate-400">Upload drawings first</div>}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}

function Step({ n, title, muted, children }: { n: number; title: string; muted?: boolean; children: React.ReactNode }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${muted ? "opacity-60" : ""}`}>
      <h2 className="mb-4 flex items-center gap-3 text-lg font-medium">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-sm text-white">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatusPill({ ok, text }: { ok: boolean | null; text: string }) {
  const color = ok === null ? "bg-slate-100 text-slate-600" : ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700";
  const dot = ok === null ? "bg-slate-400" : ok ? "bg-green-500" : "bg-red-500";
  return (
    <span className={`inline-flex max-w-full items-center gap-2 rounded-full px-3 py-1 text-sm ${color}`}>
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <span className="truncate">{text}</span>
    </span>
  );
}

function ProjectPicker({
  projects,
  current,
  onSelect,
  onCreated,
  onDelete,
  disabled,
}: {
  projects: Project[];
  current: Project | null;
  onSelect: (p: Project) => void;
  onCreated: (p: Project) => void;
  onDelete: (p: Project) => void;
  disabled: boolean;
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [error, setError] = useState("");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const p = await api.createProject({ name: name.trim(), client: client.trim() || undefined });
      onCreated(p);
      setCreating(false);
      setName("");
      setClient("");
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (creating || (projects.length === 0 && !disabled)) {
    return (
      <form onSubmit={create} className="flex flex-col gap-3 sm:flex-row">
        <input
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          placeholder="Project name, e.g. Oficinas Ejército Nacional – 3er nivel"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <input
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none sm:w-48"
          placeholder="Client (optional)"
          value={client}
          onChange={(e) => setClient(e.target.value)}
        />
        <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700" type="submit">
          Create project
        </button>
        {projects.length > 0 && (
          <button type="button" className="text-sm text-slate-500" onClick={() => setCreating(false)}>
            Cancel
          </button>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <select
        className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        value={current?.id ?? ""}
        onChange={(e) => {
          const p = projects.find((x) => x.id === Number(e.target.value));
          if (p) onSelect(p);
        }}
        disabled={disabled}
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
            {p.client ? ` — ${p.client}` : ""}
          </option>
        ))}
      </select>
      <button
        className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
        onClick={() => setCreating(true)}
        disabled={disabled}
      >
        + New project
      </button>
      {current && (
        <button
          className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
          onClick={() => onDelete(current)}
          disabled={disabled}
        >
          Delete project
        </button>
      )}
    </div>
  );
}

function DropZone({ onFiles, busy }: { onFiles: (files: File[]) => void; busy: boolean }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFiles(Array.from(e.dataTransfer.files));
      }}
      onClick={() => !busy && input.current?.click()}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-10 text-center transition ${
        over ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400"
      } ${busy ? "cursor-wait opacity-60" : ""}`}
    >
      <p className="font-medium">{busy ? "Processing drawings…" : "Drag AutoCAD files (.dwg or .dxf) here, or click to choose"}</p>
      <p className="mt-1 text-sm text-slate-500">You can select several at once. Each takes a second or two.</p>
      <input
        ref={input}
        type="file"
        accept=".dwg,.dxf"
        multiple
        hidden
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </div>
  );
}

function UploadIcon({ state }: { state: UploadRow["state"] }) {
  if (state === "working")
    return <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />;
  const map = { waiting: ["○", "text-slate-400"], done: ["✓", "text-green-600"], duplicate: ["=", "text-amber-600"], failed: ["✕", "text-red-600"] } as const;
  const [icon, color] = map[state];
  return <span className={`w-4 text-center font-bold ${color}`}>{icon}</span>;
}

function DrawingsTable({ drawings, onDelete }: { drawings: Drawing[]; onDelete: (d: Drawing) => void }) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr>
              <th className="py-2 pr-4 font-medium">Drawing</th>
              <th className="py-2 pr-4 font-medium">Version</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 text-right font-medium">Objects</th>
              <th className="py-2 pr-4 text-right font-medium">Symbols</th>
              <th className="py-2 pr-4 text-right font-medium">Labels</th>
              <th className="py-2 pr-4 font-medium">Uploaded</th>
              <th className="py-2 font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {drawings.map((d) => {
              const v = d.versions[d.versions.length - 1];
              if (!v) return null;
              const ready = v.status === "ready";
              return (
                <tr key={d.id} className="hover:bg-slate-50">
                  <td className="py-2.5 pr-4 font-medium">
                    {ready ? (
                      <Link href={`/drawings/${v.id}`} className="hover:text-blue-700 hover:underline">
                        {d.name}
                      </Link>
                    ) : (
                      d.name
                    )}
                    <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-500">
                      {v.file_format}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    v{v.version}
                    {d.versions.length > 1 && (
                      <span className="ml-1 text-xs text-slate-400">of {d.versions.length}</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4">
                    {ready ? (
                      <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">Ready</span>
                    ) : v.status === "failed" ? (
                      <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700" title={v.error ?? ""}>
                        Failed
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">Pending</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{v.object_count?.toLocaleString() ?? "—"}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{v.symbol_count?.toLocaleString() ?? "—"}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{v.label_count?.toLocaleString() ?? "—"}</td>
                  <td className="py-2.5 pr-4 whitespace-nowrap text-slate-500">{new Date(v.uploaded_at).toLocaleString()}</td>
                  <td className="py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {ready && (
                        <Link
                          href={`/drawings/${v.id}`}
                          className="whitespace-nowrap rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium hover:bg-white"
                        >
                          Open →
                        </Link>
                      )}
                      <button
                        onClick={() => onDelete(d)}
                        title="Delete this drawing and all its versions"
                        className="rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-700"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <dl className="mt-4 grid gap-x-6 gap-y-1 rounded-lg bg-slate-50 p-3 text-xs text-slate-500 sm:grid-cols-2">
        <div><dt className="inline font-medium text-slate-700">Version</dt> — v1 is the first upload of a sheet. Uploading a changed file of the same name creates v2.</div>
        <div><dt className="inline font-medium text-slate-700">Objects</dt> — every element in the drawing: lines, arcs, symbols, texts.</div>
        <div><dt className="inline font-medium text-slate-700">Symbols</dt> — placed blocks, e.g. light fixtures, outlets, desks.</div>
        <div><dt className="inline font-medium text-slate-700">Labels</dt> — text notes such as &quot;tubo P.D.G. 25 mm&quot;.</div>
      </dl>
    </div>
  );
}
