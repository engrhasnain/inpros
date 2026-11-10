"use client";

import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Button, Card, Chip, ErrorNote, FileButton, Td, Th, useAsync } from "@/components/ui";
import { api, downloadReport, qty, type FieldView } from "@/lib/api";

const today = () => new Date().toISOString().slice(0, 10);

function FieldPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [view, setView] = useState<FieldView | null>(null);
  const [entry, setEntry] = useState({ fecha: today(), clave: "", cantidad: "", zona: "", nota: "", reportado_por: "" });
  const { busy, error, run } = useAsync();

  useEffect(() => {
    run(() => api.getField(projectId).then(setView));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per project
  }, [projectId]);

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const v = await api.addField(projectId, {
        fecha: entry.fecha, clave: entry.clave, cantidad: Number(entry.cantidad),
        zona: entry.zona || undefined, nota: entry.nota || undefined, reportado_por: entry.reportado_por || undefined,
      });
      setView(v);
      setEntry({ ...entry, cantidad: "", nota: "" });
    });
  };

  const input = "mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm";

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card title="Report progress from site">
          <form onSubmit={add} className="space-y-3 p-4 text-sm">
            <label className="block"><span className="text-xs text-slate-500">Date</span>
              <input type="date" required value={entry.fecha} onChange={(e) => setEntry({ ...entry, fecha: e.target.value })} className={input} /></label>
            <label className="block"><span className="text-xs text-slate-500">Catalog item</span>
              <select required value={entry.clave} onChange={(e) => setEntry({ ...entry, clave: e.target.value })} className={`${input} bg-white`}>
                <option value="">— choose —</option>
                {view?.progress.map((p) => <option key={p.clave} value={p.clave}>{p.clave} · {p.descripcion.slice(0, 50)}</option>)}
              </select></label>
            <label className="block"><span className="text-xs text-slate-500">Quantity installed</span>
              <input type="number" step="any" min="0" required value={entry.cantidad} onChange={(e) => setEntry({ ...entry, cantidad: e.target.value })} className={input} /></label>
            <label className="block"><span className="text-xs text-slate-500">Zone / frente</span>
              <input value={entry.zona} onChange={(e) => setEntry({ ...entry, zona: e.target.value })} className={input} /></label>
            <label className="block"><span className="text-xs text-slate-500">Note</span>
              <input value={entry.nota} onChange={(e) => setEntry({ ...entry, nota: e.target.value })} className={input} /></label>
            <label className="block"><span className="text-xs text-slate-500">Reported by</span>
              <input value={entry.reportado_por} onChange={(e) => setEntry({ ...entry, reportado_por: e.target.value })} className={input} /></label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="primary" disabled={busy}>Add entry</Button>
              <FileButton label="Upload site report (.xlsx)" accept=".xlsx,.xlsm" busy={busy} onFile={(f) => run(() => api.uploadField(projectId, f).then(setView))} />
            </div>
            <p className="text-xs text-slate-500">Excel columns: Fecha, Clave, Cantidad, Zona, Nota, Reportado por.</p>
          </form>
        </Card>

        <div className="space-y-5">
          <Card
            title="Progress per catalog item"
            actions={<Button onClick={() => run(() => downloadReport(api.fieldReportUrl(projectId), "reporte_avance.pdf"))} disabled={busy}>Progress report (PDF)</Button>}
          >
            {!view || view.progress.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">Upload the contract catalog first.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-slate-500"><tr><Th>Clave</Th><Th>Item</Th><Th right>Contract</Th><Th right>Installed</Th><Th>Progress</Th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {view.progress.map((p) => (
                      <tr key={p.clave}>
                        <Td className="whitespace-nowrap font-medium">{p.clave}</Td>
                        <Td className="min-w-[16rem]">{p.descripcion}</Td>
                        <Td right>{qty(p.contract)} <span className="text-xs text-slate-400">{p.unidad}</span></Td>
                        <Td right>{qty(p.installed)}</Td>
                        <Td className="min-w-[10rem]">
                          <div className="flex items-center gap-2">
                            <div className="h-2 flex-1 rounded-full bg-slate-100">
                              <div className={`h-2 rounded-full ${p.percent && p.percent > 100 ? "bg-red-500" : "bg-blue-600"}`} style={{ width: `${Math.min(100, p.percent ?? 0)}%` }} />
                            </div>
                            <span className="w-12 text-right text-xs tabular-nums">{p.percent === null ? "—" : `${p.percent}%`}</span>
                          </div>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={`Site log (${view?.entries.length ?? 0} entries)`}>
            {view && view.entries.length > 0 ? (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white text-slate-500"><tr><Th>Date</Th><Th>Clave</Th><Th right>Qty</Th><Th>Zone</Th><Th>Reported by</Th><Th>Note</Th><Th /></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {view.entries.map((e) => (
                      <tr key={e.id}>
                        <Td className="whitespace-nowrap">{e.fecha}</Td>
                        <Td className="whitespace-nowrap font-medium">{e.clave} {!e.in_catalog && <Chip tone="red">not in catalog</Chip>}</Td>
                        <Td right>{qty(e.cantidad)}</Td>
                        <Td>{e.zona ?? "—"}</Td>
                        <Td>{e.reportado_por ?? "—"}</Td>
                        <Td className="text-slate-600">{e.nota}</Td>
                        <Td><button className="text-xs text-slate-400 hover:text-red-700" disabled={busy} onClick={() => run(() => api.deleteField(e.id).then(setView))}>Delete</button></Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="p-4 text-sm text-slate-500">No site progress reported yet.</p>
            )}
          </Card>
          <p className="text-xs text-slate-500">Site progress is also used by the estimación check: a claim above what the site reported is flagged for review.</p>
        </div>
      </div>
    </main>
  );
}

export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <FieldPage />
    </Suspense>
  );
}
