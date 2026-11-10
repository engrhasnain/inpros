"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Button, Card, Chip, ErrorNote, Stat, Td, Th, useAsync } from "@/components/ui";
import { api, downloadReport, money, type BidEvaluation, type EstimacionSummary, type Readiness } from "@/lib/api";

function ReportsPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [ests, setEsts] = useState<EstimacionSummary[]>([]);
  const [bids, setBids] = useState<BidEvaluation | null>(null);
  const [bidder, setBidder] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const { busy, error, run } = useAsync();

  useEffect(() => {
    run(async () => {
      const [r, e, b] = await Promise.all([api.readiness(projectId), api.listEstimaciones(projectId), api.getBids(projectId)]);
      setReady(r);
      setEsts(e);
      setBids(b);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per project
  }, [projectId]);

  const uploadBid = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !bidder.trim()) return;
    run(async () => {
      setBids(await api.uploadBid(projectId, file, bidder.trim()));
      setBidder("");
      setFile(null);
    });
  };

  const bidderNames = bids ? [...bids.bidders].sort((a, b) => a.bidder.localeCompare(b.bidder)).map((b) => b.bidder) : [];

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />

      {ready && !ready.ready && (
        <p className="mb-5 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Reports are blocked until the project details are complete ({[...ready.missing, ...ready.problems].join("; ")}).{" "}
          <Link href={`/projects/${projectId}/details`} className="font-medium underline">Complete project details →</Link>
        </p>
      )}

      <Card title="Technical reports (dictamen técnico de estimación)">
        {ests.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">Check an estimación first; its dictamen appears here.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-500"><tr><Th>Estimación</Th><Th>Period</Th><Th>Status</Th><Th right>Claimed</Th><Th right>Approvable</Th><Th /></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {ests.map((e) => (
                <tr key={e.id}>
                  <Td className="font-medium">No. {e.numero}</Td>
                  <Td>{e.periodo ?? "—"}</Td>
                  <Td>{e.status === "approved" ? <Chip tone="green">Approved</Chip> : <Chip tone="blue">Checked</Chip>}</Td>
                  <Td right>{money(e.totals.claimed_amount)}</Td>
                  <Td right>{money(e.totals.approvable_amount)}</Td>
                  <Td right>
                    <Button variant="primary" disabled={busy || !ready?.ready}
                      onClick={() => run(() => downloadReport(api.dictamenUrl(e.id), `dictamen_estimacion_${String(e.numero).padStart(2, "0")}.pdf`))}>
                      Dictamen (PDF)
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
          Contract number, scope and signatories come from <Link href={`/projects/${projectId}/details`} className="text-blue-700">project details</Link>;
          quantities and amounts come from the verified check. The site progress report is on the Field progress tab.
        </p>
      </Card>

      <div className="mt-5">
        <Card
          title="Bid evaluation (evaluación de propuestas)"
          actions={bids && bids.bidders.length > 0 && (
            <Button variant="primary" disabled={busy || !ready?.ready} onClick={() => run(() => downloadReport(api.bidsReportUrl(projectId), "evaluacion_propuestas.pdf"))}>
              Bid evaluation (PDF)
            </Button>
          )}
        >
          <form onSubmit={uploadBid} className="flex flex-wrap items-end gap-3 border-b border-slate-100 p-4 text-sm">
            <label><span className="text-xs text-slate-500">Bidder</span>
              <input value={bidder} onChange={(e) => setBidder(e.target.value)} placeholder="Company name" className="mt-1 block w-56 rounded-lg border border-slate-300 px-2 py-1.5" /></label>
            <input type="file" accept=".xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-xs" />
            <Button type="submit" variant="primary" disabled={busy || !file || !bidder.trim()}>Add bid</Button>
            <span className="text-xs text-slate-500">Excel with Clave and P.U. per catalog item. Same bidder again = replaced.</span>
          </form>

          {bids && bids.bidders.length > 0 && (
            <div className="space-y-4 p-4">
              <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Stat label="Budget (catalog)" value={money(bids.budget_total)} />
                <Stat label="Bids" value={bids.bidders.length} hint={`${bids.bidders.filter((b) => b.complete).length} complete`} />
                <Stat label="Lowest complete" value={bids.recommended ?? "—"} tone="green" />
                <Stat label="Prices to clarify" value={bids.bidders.reduce((s, b) => s + b.price_outliers.length, 0)} hint="±25% from the median" tone="amber" />
              </section>
              <p className="rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-900">{bids.recommendation_note}</p>
              <table className="w-full text-sm">
                <thead className="text-slate-500"><tr><Th>Rank</Th><Th>Bidder</Th><Th right>Total</Th><Th right>vs budget</Th><Th>Missing items</Th><Th>Prices to clarify</Th><Th /></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {bids.bidders.map((b) => (
                    <tr key={b.bid_id}>
                      <Td className="font-semibold">{b.rank}</Td>
                      <Td className="font-medium">{b.bidder} {!b.complete && <Chip tone="red">incomplete</Chip>}</Td>
                      <Td right>{money(b.total)}</Td>
                      <Td right className={b.vs_budget > 0 ? "text-amber-700" : "text-green-700"}>{b.vs_budget_pct !== null ? `${b.vs_budget_pct > 0 ? "+" : ""}${b.vs_budget_pct}%` : "—"}</Td>
                      <Td>{b.missing_items.join(", ") || "—"}</Td>
                      <Td>{b.price_outliers.join(", ") || "—"}</Td>
                      <Td><button className="text-xs text-slate-400 hover:text-red-700" disabled={busy} onClick={() => run(() => api.deleteBid(b.bid_id).then(setBids))}>Remove</button></Td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <details className="text-sm">
                <summary className="cursor-pointer font-medium text-blue-700">Unit prices per item</summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-slate-500"><tr><Th>Clave</Th><Th>Item</Th><Th right>Budget P.U.</Th><Th right>Median</Th>{bidderNames.map((n) => <Th key={n} right>{n}</Th>)}</tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {bids.items.map((it) => (
                        <tr key={it.clave}>
                          <Td className="font-medium">{it.clave}</Td>
                          <Td className="min-w-[14rem]">{it.descripcion}</Td>
                          <Td right>{money(it.budget_unit_price)}</Td>
                          <Td right>{money(it.median_unit_price)}</Td>
                          {bidderNames.map((n) => {
                            const c = it.bidders[n];
                            const tone = c.flag === "missing" || c.flag === "high" ? "bg-red-50 text-red-700" : c.flag === "low" ? "bg-amber-50 text-amber-800" : "";
                            return <Td key={n} right className={tone}>{c.unit_price === null ? "missing" : money(c.unit_price)}{c.flag && c.flag !== "missing" ? ` (${c.flag})` : ""}</Td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )}
        </Card>
      </div>
    </main>
  );
}

export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <ReportsPage />
    </Suspense>
  );
}
