"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Card, Chip } from "@/components/ui";
import { api, money, qty, type Analysis, type Comparison, type DrawingTakeoff, type DrawingVersion, type DrawingVersionDetail } from "@/lib/api";

type Takeoff = Omit<DrawingTakeoff, "drawing_id" | "drawing_name" | "version_id" | "version">;

type Tab = "layers" | "symbols" | "labels";

function DrawingPage() {
  const params = useParams<{ id: string }>();
  const versionId = Number(params.id);
  const [version, setVersion] = useState<DrawingVersionDetail | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [takeoff, setTakeoff] = useState<Takeoff | null>(null);
  const [versions, setVersions] = useState<DrawingVersion[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!Number.isFinite(versionId)) return;
    Promise.all([api.getVersion(versionId), api.getAnalysis(versionId), api.getTakeoff(versionId)])
      .then(async ([v, a, t]) => {
        setVersion(v);
        setAnalysis(a);
        setTakeoff(t);
        const drawings = await api.listDrawings(v.project_id);
        setVersions(drawings.find((d) => d.id === v.drawing_id)?.versions ?? []);
      })
      .catch((e: Error) => setError(e.message));
  }, [versionId]);

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      {version ? <ProjectNav projectId={version.project_id} /> : (
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">← Back to project</Link>
      )}

      {error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}
      {!error && (!version || !analysis) && <p className="mt-6 text-sm text-slate-500">Loading drawing…</p>}

      {version && analysis && (
        <>
          <Header version={version} analysis={analysis} />
          {versions.length > 1 && <VersionBar versions={versions} current={version.id} />}
          <Stats analysis={analysis} />
          <Viewer src={api.previewUrl(version.id)} />
          {versions.length > 1 && <Revisions drawingId={version.drawing_id} versions={versions} current={version.version} />}
          {takeoff && <TakeoffPanel takeoff={takeoff} projectId={version.project_id} />}
          <Details analysis={analysis} />
        </>
      )}
    </main>
  );
}

function VersionBar({ versions, current }: { versions: DrawingVersion[]; current: number }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
      <span className="text-slate-500">Versions:</span>
      {versions.map((v) => (
        <Link
          key={v.id}
          href={`/drawings/${v.id}`}
          className={`rounded-lg border px-3 py-1 ${v.id === current ? "border-blue-600 bg-blue-50 font-medium text-blue-700" : "border-slate-300 hover:bg-slate-50"}`}
        >
          v{v.version} <span className="text-xs text-slate-400">{v.file_format.toUpperCase()} · {new Date(v.uploaded_at).toLocaleDateString()}</span>
        </Link>
      ))}
    </div>
  );
}

function Revisions({ drawingId, versions, current }: { drawingId: number; versions: DrawingVersion[]; current: number }) {
  const ready = versions.filter((v) => v.status === "ready").map((v) => v.version);
  const [newV, setNewV] = useState(current === ready[0] ? ready[ready.length - 1] : current);
  const [oldV, setOldV] = useState(ready[Math.max(0, ready.indexOf(newV) - 1)] ?? ready[0]);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (oldV === newV) return;
    api.compare(drawingId, oldV, newV).then((c) => { setCmp(c); setError(""); }).catch((e: Error) => setError(e.message));
  }, [drawingId, oldV, newV]);

  const sel = (value: number, set: (n: number) => void) => (
    <select value={value} onChange={(e) => set(Number(e.target.value))} className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm">
      {ready.map((n) => <option key={n} value={n}>v{n}</option>)}
    </select>
  );
  const shown = cmp && oldV !== newV ? cmp : null;

  return (
    <div className="mt-5">
      <Card
        title="Revision changes"
        actions={<span className="flex items-center gap-2 text-sm">compare {sel(oldV, setOldV)} → {sel(newV, setNewV)}</span>}
      >
        {error && <p className="px-4 py-3 text-sm text-red-700">{error}</p>}
        {oldV === newV && <p className="px-4 py-3 text-sm text-slate-500">Pick two different versions.</p>}
        {shown && (
          <div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 border-b border-slate-100 px-4 py-3 text-sm">
              <span><b>{shown.quantity_changes.length}</b> quantity changes</span>
              <span>Cost impact (priced items): <b className={shown.cost_impact_total > 0 ? "text-amber-700" : shown.cost_impact_total < 0 ? "text-green-700" : ""}>{shown.cost_impact_total > 0 ? "+" : ""}{money(shown.cost_impact_total)}</b></span>
              {shown.unpriced_changes > 0 && <span className="text-slate-500">{shown.unpriced_changes} change(s) not linked to a catalog price</span>}
              <span className="text-slate-500">objects {shown.objects.old.toLocaleString()} → {shown.objects.new.toLocaleString()}</span>
            </div>
            {shown.quantity_changes.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No quantity changes between these versions.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Sheet</th>
                    <th className="px-4 py-2 text-left font-medium">Item</th>
                    <th className="px-4 py-2 text-right font-medium">v{shown.old.version}</th>
                    <th className="px-4 py-2 text-right font-medium">v{shown.new.version}</th>
                    <th className="px-4 py-2 text-right font-medium">Change</th>
                    <th className="px-4 py-2 text-right font-medium">Cost impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {shown.quantity_changes.map((c) => (
                    <tr key={`${c.sheet}|${c.key}`}>
                      <td className="px-4 py-2"><Chip tone="blue">{c.sheet}</Chip></td>
                      <td className="px-4 py-2">
                        <span className="font-medium">{c.description}</span> <span className="text-xs text-slate-400">{c.layer}</span>
                        {c.catalog_clave && <span className="ml-2 text-xs text-slate-500">→ {c.catalog_clave}</span>}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{qty(c.old)} {c.unit}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{qty(c.new)} {c.unit}</td>
                      <td className={`px-4 py-2 text-right font-semibold tabular-nums ${c.delta > 0 ? "text-amber-700" : "text-green-700"}`}>{c.delta > 0 ? "+" : ""}{qty(c.delta)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{c.cost_impact === null ? <span className="text-xs text-slate-400">not priced</span> : `${c.cost_impact > 0 ? "+" : ""}${money(c.cost_impact)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {(shown.layers_added.length > 0 || shown.layers_removed.length > 0 || shown.labels_added.length > 0 || shown.labels_removed.length > 0) && (
              <div className="grid gap-3 border-t border-slate-100 px-4 py-3 text-xs text-slate-600 sm:grid-cols-2">
                {shown.labels_added.length > 0 && <div><b>Labels added:</b> {shown.labels_added.slice(0, 12).join(" · ")}</div>}
                {shown.labels_removed.length > 0 && <div><b>Labels removed:</b> {shown.labels_removed.slice(0, 12).join(" · ")}</div>}
                {shown.layers_added.length > 0 && <div><b>Layers added:</b> {shown.layers_added.join(", ")}</div>}
                {shown.layers_removed.length > 0 && <div><b>Layers removed:</b> {shown.layers_removed.join(", ")}</div>}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function TakeoffPanel({ takeoff, projectId }: { takeoff: Takeoff; projectId: number }) {
  const excl = Object.entries(takeoff.excluded);
  return (
    <div className="mt-5">
      <Card
        title={`Quantities from this drawing (${takeoff.sheets.length} sheet${takeoff.sheets.length > 1 ? "s" : ""})`}
        actions={<Link href={`/projects/${projectId}/quantities`} className="text-xs font-medium text-blue-700">All project quantities →</Link>}
      >
        {excl.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b border-slate-100 px-4 py-2 text-xs text-slate-500">
            Excluded: {excl.map(([r, n]) => <Chip key={r} tone="slate">{n} {r}</Chip>)}
          </div>
        )}
        {takeoff.items.length === 0 ? (
          <p className="px-4 py-3 text-sm text-slate-500">No electrical symbols or runs found on this drawing.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Sheet</th>
                <th className="px-4 py-2 text-left font-medium">Item</th>
                <th className="px-4 py-2 text-right font-medium">Quantity</th>
                <th className="px-4 py-2 text-left font-medium">How</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {takeoff.items.map((it) => (
                <tr key={`${it.sheet}|${it.key}`}>
                  <td className="px-4 py-2"><Chip tone="blue">{it.sheet}</Chip></td>
                  <td className="px-4 py-2"><span className="font-medium">{it.description}</span> <span className="text-xs text-slate-400">{it.layer}</span></td>
                  <td className="px-4 py-2 text-right font-semibold tabular-nums">{qty(it.quantity)} {it.unit}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{it.method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function Header({ version, analysis }: { version: DrawingVersionDetail; analysis: Analysis }) {
  return (
    <header className="mt-3 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">{version.drawing_name}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {version.original_filename} · {version.file_format.toUpperCase()} ({version.cad_version}) ·{" "}
          {(version.size_bytes / 1024 / 1024).toFixed(1)} MB · uploaded {new Date(version.uploaded_at).toLocaleString()}
        </p>
      </div>
      <div className="text-right text-sm">
        <span className="rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">
          Version {version.version} of {version.total_versions}
        </span>
        <p className="mt-1 text-xs text-slate-400">read with {analysis.reader}</p>
      </div>
    </header>
  );
}

function Stats({ analysis }: { analysis: Analysis }) {
  const t = analysis.totals;
  const cards = [
    { label: "Objects", value: t.objects, hint: "every line, arc, symbol and text" },
    { label: "Layers", value: t.layers, hint: "groups, e.g. LUMINARIOS, TUBERIA" },
    { label: "Symbols placed", value: t.symbols_placed, hint: `${t.symbol_types} kinds, e.g. fixtures, desks` },
    { label: "Text labels", value: t.labels, hint: `${t.unique_labels} different texts` },
  ];
  return (
    <section className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{c.label}</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">{c.value.toLocaleString()}</div>
          <div className="mt-1 text-xs text-slate-400">{c.hint}</div>
        </div>
      ))}
    </section>
  );
}

function Viewer({ src }: { src: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [loaded, setLoaded] = useState(false);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  // Wheel zoom around the cursor. Registered manually so it can preventDefault (passive: false).
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      setView((v) => {
        const scale = Math.min(40, Math.max(1, v.scale * (e.deltaY < 0 ? 1.2 : 1 / 1.2)));
        const k = scale / v.scale;
        return scale === 1 ? { scale: 1, x: 0, y: 0 } : { scale, x: mx - (mx - v.x) * k, y: my - (my - v.y) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const zoomBy = (f: number) => {
    const el = box.current;
    if (!el) return;
    const cx = el.clientWidth / 2;
    const cy = el.clientHeight / 2;
    setView((v) => {
      const scale = Math.min(40, Math.max(1, v.scale * f));
      const k = scale / v.scale;
      return scale === 1 ? { scale: 1, x: 0, y: 0 } : { scale, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
    });
  };

  return (
    <section className="mt-5 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
        <h2 className="text-sm font-medium">Drawing</h2>
        <div className="flex items-center gap-2 text-sm">
          <span className="hidden text-xs text-slate-400 sm:inline">Scroll to zoom · drag to move</span>
          <button className="h-8 w-8 rounded-lg border border-slate-300 hover:bg-slate-50" onClick={() => zoomBy(1 / 1.5)} aria-label="Zoom out">
            −
          </button>
          <span className="w-12 text-center tabular-nums text-slate-500">{Math.round(view.scale * 100)}%</span>
          <button className="h-8 w-8 rounded-lg border border-slate-300 hover:bg-slate-50" onClick={() => zoomBy(1.5)} aria-label="Zoom in">
            +
          </button>
          <button className="rounded-lg border border-slate-300 px-3 py-1 hover:bg-slate-50" onClick={() => setView({ scale: 1, x: 0, y: 0 })}>
            Fit
          </button>
        </div>
      </div>
      <div
        ref={box}
        className="relative h-[60vh] min-h-[320px] cursor-grab touch-none select-none overflow-hidden bg-white active:cursor-grabbing"
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
        }}
        onPointerUp={() => (drag.current = null)}
        onDoubleClick={() => zoomBy(2)}
      >
        {!loaded && <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">Drawing the plan…</p>}
        {/* eslint-disable-next-line @next/next/no-img-element -- SVG from our API, sized by the viewer */}
        <img
          src={src}
          alt="Drawing preview"
          draggable={false}
          onLoad={() => setLoaded(true)}
          className="absolute left-0 top-0 h-full w-full object-contain"
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: "0 0" }}
        />
      </div>
    </section>
  );
}

function Details({ analysis }: { analysis: Analysis }) {
  const [tab, setTab] = useState<Tab>("layers");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const layers = useMemo(() => analysis.layers.filter((l) => l.name.toLowerCase().includes(q)), [analysis, q]);
  const symbols = useMemo(() => analysis.symbols.filter((s) => s.name.toLowerCase().includes(q)), [analysis, q]);
  const labels = useMemo(() => analysis.labels.filter((l) => l.text.toLowerCase().includes(q)), [analysis, q]);

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "layers", label: "Layers", count: analysis.layers.length },
    { id: "symbols", label: "Symbols", count: analysis.symbols.length },
    { id: "labels", label: "Labels", count: analysis.labels.length },
  ];

  return (
    <section className="mt-5 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-2">
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tab === t.id ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.label} <span className={tab === t.id ? "text-blue-100" : "text-slate-400"}>{t.count}</span>
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${tab}…`}
          className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none sm:w-64"
        />
      </div>

      <div className="max-h-[480px] overflow-auto">
        {tab === "layers" && (
          <Table
            head={["Layer", "Objects", "Line length", "Symbols on this layer"]}
            align={["left", "right", "right", "left"]}
            rows={layers.map((l) => [
              <span key="n" className="font-medium">{l.name}</span>,
              l.objects.toLocaleString(),
              l.length > 0 ? `${l.length.toLocaleString(undefined, { maximumFractionDigits: 1 })} m` : "—",
              l.symbols.length ? l.symbols.map((s) => `${s.name} ×${s.count}`).join(", ") : "—",
            ])}
          />
        )}
        {tab === "symbols" && (
          <Table
            head={["Symbol (block)", "Placed", "On layer", "Attribute examples"]}
            align={["left", "right", "left", "left"]}
            rows={symbols.map((s) => [
              <span key="n" className="font-medium">
                {s.name}
                {s.anonymous && <span className="ml-2 text-xs font-normal text-slate-400">unnamed internal block</span>}
              </span>,
              s.count.toLocaleString(),
              s.layers.map((l) => l.name).join(", "),
              s.attribs.length ? s.attribs.slice(0, 3).map((a) => a.value).join(", ") : "—",
            ])}
          />
        )}
        {tab === "labels" && (
          <Table
            head={["Text", "Times", "Layer"]}
            align={["left", "right", "left"]}
            rows={labels.map((l) => [<span key="t" className="whitespace-pre-wrap">{l.text}</span>, l.count.toLocaleString(), l.layers.join(", ")])}
          />
        )}
      </div>

      <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
        Line length is the total of lines, arcs and polylines on the layer, in drawing units
        {analysis.units === "unitless" ? " (the file does not state units; these plans are drawn in metres)" : ` (${analysis.units})`}.
        Trays drawn as two parallel edges are counted twice here — the Quantities panel above measures the run instead.
        {analysis.notes.length > 0 && <span className="block pt-1 text-slate-400">Not measured or drawn: {analysis.notes.join("; ")}.</span>}
      </div>
    </section>
  );
}

function Table({ head, align, rows }: { head: string[]; align: ("left" | "right")[]; rows: React.ReactNode[][] }) {
  if (rows.length === 0) return <p className="p-4 text-sm text-slate-500">Nothing matches.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="sticky top-0 bg-white text-slate-500 shadow-[0_1px_0_#f1f5f9]">
        <tr>
          {head.map((h, i) => (
            <th key={h} className={`px-4 py-2 font-medium ${align[i] === "right" ? "text-right" : "text-left"}`}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r, i) => (
          <tr key={i} className="hover:bg-slate-50">
            {r.map((cell, j) => (
              <td key={j} className={`px-4 py-2 align-top ${align[j] === "right" ? "text-right tabular-nums" : ""}`}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}


// useParams() reads URL data, which must sit inside a Suspense boundary (cacheComponents).
export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <DrawingPage />
    </Suspense>
  );
}
