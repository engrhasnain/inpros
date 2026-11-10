"use client";

import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Button, Card, Chip, ErrorNote, Stat, Td, Th, useAsync } from "@/components/ui";
import { api, downloadReport, money, qty, type EstimacionLineResult, type EstimacionResult, type EstimacionSummary } from "@/lib/api";

const SEVERITY: Record<EstimacionLineResult["severity"], { tone: "green" | "red" | "amber" | "blue"; row: string }> = {
  ok: { tone: "green", row: "" },
  info: { tone: "blue", row: "" },
  warning: { tone: "amber", row: "bg-amber-50/40" },
  error: { tone: "red", row: "bg-red-50/40" },
};

function EstimacionesPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [list, setList] = useState<EstimacionSummary[]>([]);
  const [current, setCurrent] = useState<EstimacionResult | null>(null);
  const [numero, setNumero] = useState(1);
  const [periodo, setPeriodo] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [filter, setFilter] = useState<"all" | "issues">("all");
  const { busy, error, run } = useAsync();

  const refresh = useCallback(async (select?: number) => {
    const l = await api.listEstimaciones(projectId);
    setList(l);
    setNumero((l.at(-1)?.numero ?? 0) + 1);
    const id = select ?? l.at(-1)?.id;
    setCurrent(id ? await api.getEstimacion(id) : null);
  }, [projectId]);

  useEffect(() => {
    run(() => refresh());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per project
  }, [projectId]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    run(async () => {
      const r = await api.uploadEstimacion(projectId, file, numero, periodo);
      setFile(null);
      setPeriodo("");
      await refresh(r.id);
    });
  };

  const lines = current ? (filter === "issues" ? current.lines.filter((l) => l.severity !== "ok") : current.lines) : [];
  const t = current?.totals;

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Card title="Check a contractor's estimación">
          <form onSubmit={submit} className="space-y-3 px-4 py-4 text-sm">
            <p className="text-slate-600">
              Excel with at least <b>Clave</b> and <b>Cantidad esta estimación</b> (Unidad, P.U. and Cantidad anterior are checked when present).
              Each line is compared with the contract catalog, earlier approved estimaciones and the drawing quantities.
            </p>
            <div className="flex gap-3">
              <label className="w-24">
                <span className="text-xs text-slate-500">Number</span>
                <input type="number" min={1} value={numero} onChange={(e) => setNumero(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5" />
              </label>
              <label className="flex-1">
                <span className="text-xs text-slate-500">Period (optional)</span>
                <input value={periodo} onChange={(e) => setPeriodo(e.target.value)} placeholder="01–15 oct 2026"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5" />
              </label>
            </div>
            <input type="file" accept=".xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-xs" />
            <Button type="submit" variant="primary" disabled={!file || busy}>{busy ? "Checking…" : "Upload and check"}</Button>
          </form>

          {list.length > 0 && (
            <ul className="divide-y divide-slate-100 border-t border-slate-100">
              {list.map((e) => (
                <li key={e.id}>
                  <button
                    onClick={() => run(async () => setCurrent(await api.getEstimacion(e.id)))}
                    className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left text-sm hover:bg-slate-50 ${current?.id === e.id ? "bg-blue-50" : ""}`}
                  >
                    <span>
                      <span className="font-medium">Estimación {e.numero}</span>
                      <span className="block text-xs text-slate-500">{e.periodo ?? e.source_filename}</span>
                    </span>
                    <span className="text-right">
                      {e.status === "approved" ? <Chip tone="green">Approved</Chip> : e.totals.errors ? <Chip tone="red">{e.totals.errors} to adjust</Chip> : <Chip tone="blue">Checked</Chip>}
                      <span className="block text-xs tabular-nums text-slate-500">{money(e.totals.approvable_amount)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-5">
          {!current && <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Upload an estimación to see its check.</p>}
          {current && t && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold">Estimación {current.numero}{current.periodo ? ` · ${current.periodo}` : ""}</h2>
                  <p className="text-xs text-slate-500">
                    {current.source_filename} · {current.status === "approved" ? `approved ${new Date(current.approved_at!).toLocaleString()}` : "checked, not approved yet"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <a href={api.exportUrl(current.id)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50">Export validated Excel</a>
                  <Button disabled={busy} onClick={() => run(() => downloadReport(api.dictamenUrl(current.id), `dictamen_estimacion_${String(current.numero).padStart(2, "0")}.pdf`))}>
                    Dictamen (PDF)
                  </Button>
                  {current.status !== "approved" && (
                    <>
                      <Button variant="danger" disabled={busy} onClick={() => run(async () => { await api.deleteEstimacion(current.id); await refresh(); })}>Delete</Button>
                      <Button variant="primary" disabled={busy} onClick={() => run(async () => { const r = await api.approveEstimacion(current.id); await refresh(r.id); })}>
                        Approve approvable amounts
                      </Button>
                    </>
                  )}
                </div>
              </div>

              <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Stat label="Claimed" value={money(t.claimed_amount)} hint={`${t.lines} lines`} />
                <Stat label="Approvable" value={money(t.approvable_amount)} hint="contract prices, contract limits" tone="green" />
                <Stat label="Difference" value={money(t.claimed_amount - t.approvable_amount)} hint="claimed − approvable" tone={t.claimed_amount > t.approvable_amount ? "red" : undefined} />
                <Stat label="Lines" value={`${t.ok} OK`} hint={`${t.errors} adjusted · ${t.warnings} to review · ${t.not_verified} not verifiable`} />
              </section>

            </>
          )}
        </div>
      </div>

      {current && (
        <div className="mt-5 space-y-3">
                <Card
                  title="Line by line"
                  actions={
                    <div className="flex gap-1 text-xs">
                      {(["all", "issues"] as const).map((f) => (
                        <button key={f} onClick={() => setFilter(f)} className={`rounded-lg px-2 py-1 ${filter === f ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                          {f === "all" ? "All lines" : "Only issues"}
                        </button>
                      ))}
                    </div>
                  }
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-slate-500">
                        <tr>
                          <Th>Clave</Th>
                          <Th>Concept</Th>
                          <Th right>Claimed</Th>
                          <Th right>Prev. approved</Th>
                          <Th right>Contract</Th>
                          <Th right>Drawings</Th>
                          <Th right>Approvable</Th>
                          <Th right>Amount</Th>
                          <Th>Result</Th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {lines.map((l) => (
                          <tr key={l.id} className={SEVERITY[l.severity].row}>
                            <Td className="whitespace-nowrap font-medium">{l.clave}</Td>
                            <Td className="min-w-[18rem]">
                              <div>{l.descripcion || <span className="text-slate-400">(not in catalog)</span>}</div>
                              {l.findings.length > 0 && (
                                <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
                                  {l.findings.map((f) => (
                                    <li key={f.code}>
                                      <span className={f.severity === "error" ? "text-red-700" : f.severity === "warning" ? "text-amber-700" : "text-blue-700"}>●</span> {f.message}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </Td>
                            <Td right>{qty(l.claimed)} <span className="text-xs text-slate-400">{l.unidad}</span></Td>
                            <Td right>{qty(l.previous_approved)}</Td>
                            <Td right>{qty(l.contract_quantity)}</Td>
                            <Td right>{qty(l.drawing_quantity)}</Td>
                            <Td right className="font-semibold">{qty(l.approvable)}</Td>
                            <Td right>
                              {money(l.approvable_amount)}
                              {l.claimed_amount !== l.approvable_amount && <div className="text-xs text-slate-400 line-through">{money(l.claimed_amount)}</div>}
                            </Td>
                            <Td><Chip tone={SEVERITY[l.severity].tone}>{l.result}</Chip></Td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
                <p className="text-xs text-slate-500">
                  <b>Adjusted</b>: the approvable amount was reduced (over contract, wrong price, duplicate, not in contract). <b>Review</b>: payable,
                  but something needs a look (e.g. more than the drawings show). <b>Not verified</b>: no drawing quantity linked in the catalog.
                  Approving stores the approvable quantities as &quot;previously paid&quot; for the next estimación.
                </p>
        </div>
      )}
    </main>
  );
}


// useParams() reads URL data, which must sit inside a Suspense boundary (cacheComponents).
export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <EstimacionesPage />
    </Suspense>
  );
}
