"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Card, Chip, ErrorNote, Stat, Td, Th } from "@/components/ui";
import { api, qty, type DrawingTakeoff } from "@/lib/api";

function QuantitiesPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [data, setData] = useState<DrawingTakeoff[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.getTakeoffSummary(projectId).then(setData).catch((e: Error) => setError(e.message));
  }, [projectId]);

  const all = data?.flatMap((d) => d.items) ?? [];
  const excludedTotal = data?.reduce((s, d) => s + Object.values(d.excluded).reduce((a, b) => a + b, 0), 0) ?? 0;

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />
      {!data && !error && <p className="text-sm text-slate-500">Loading quantities…</p>}

      {data && data.length === 0 && (
        <p className="rounded-lg bg-slate-100 p-4 text-sm text-slate-600">
          No drawings yet. <Link href="/" className="font-medium text-blue-700">Upload drawings first</Link>.
        </p>
      )}

      {data && data.length > 0 && (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Drawings" value={data.length} hint="latest version of each" />
            <Stat label="Sheets" value={data.reduce((s, d) => s + d.sheets.length, 0)} hint="title-block frames found" />
            <Stat label="Quantity items" value={all.length} hint={`${all.filter((i) => i.kind === "count").length} counted · ${all.filter((i) => i.kind === "length").length} measured`} />
            <Stat label="Objects excluded" value={excludedTotal.toLocaleString()} hint="outside sheets, legend, duplicates" />
          </section>

          <p className="mt-4 rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-900">
            Only electrical layers are taken off. Symbols are counted per sheet; lines are measured in metres.
            Objects outside the sheet frames, sample symbols in the legend and exact duplicates are left out — the count
            of each is shown per drawing so nothing disappears silently.
          </p>

          <div className="mt-5 space-y-5">
            {data.map((d) => {
              const excl = Object.entries(d.excluded);
              return (
                <Card
                  key={d.drawing_id}
                  title={`${d.drawing_name} · v${d.version}`}
                  actions={
                    <>
                      <span className="text-xs text-slate-500">
                        {d.sheets.length} sheet{d.sheets.length > 1 ? "s" : ""}
                        {d.zones.length ? ` · ${d.zones.length} zones` : ""}
                      </span>
                      <Link href={`/drawings/${d.version_id}`} className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium hover:bg-slate-50">
                        Open drawing →
                      </Link>
                    </>
                  }
                >
                  {excl.length > 0 && (
                    <div className="flex flex-wrap gap-2 border-b border-slate-100 px-4 py-2 text-xs text-slate-500">
                      Excluded:
                      {excl.map(([reason, n]) => (
                        <Chip key={reason} tone="slate">
                          {n} {reason}
                        </Chip>
                      ))}
                    </div>
                  )}
                  {d.items.length === 0 ? (
                    <p className="px-4 py-3 text-sm text-slate-500">No electrical symbols or runs found on this drawing (it may be a schedule or diagram — see its labels).</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="text-slate-500">
                          <tr>
                            <Th>Sheet</Th>
                            <Th>Item</Th>
                            <Th>Layer</Th>
                            <Th right>Quantity</Th>
                            <Th>Unit</Th>
                            <Th>How</Th>
                            <Th>Zones</Th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {d.items.map((it) => {
                            const id = `${d.drawing_id}|${it.sheet}|${it.key}`;
                            const zones = Object.entries(it.zones);
                            return (
                              <tr key={id} className="hover:bg-slate-50">
                                <Td><Chip tone="blue">{it.sheet}</Chip></Td>
                                <Td className="font-medium">
                                  {it.description}
                                  {it.symbol && <span className="ml-1 text-xs font-normal text-slate-400">({it.symbol})</span>}
                                </Td>
                                <Td className="text-slate-500">{it.layer}</Td>
                                <Td right className="font-semibold">{qty(it.quantity)}</Td>
                                <Td>{it.unit}</Td>
                                <Td className="text-xs text-slate-500">
                                  {it.method.startsWith("estimated") ? <Chip tone="amber">{it.method}</Chip> : it.method}
                                </Td>
                                <Td className="text-xs">
                                  {zones.length === 0 ? (
                                    <span className="text-slate-300">—</span>
                                  ) : open === id ? (
                                    <ul className="space-y-0.5">
                                      {zones.map(([z, n]) => (
                                        <li key={z}><span className="tabular-nums font-medium">{n}</span> <span className="text-slate-500">{z}</span></li>
                                      ))}
                                      <li><button className="text-blue-700" onClick={() => setOpen(null)}>hide</button></li>
                                    </ul>
                                  ) : (
                                    <button className="text-blue-700" onClick={() => setOpen(id)}>{zones.length} zones ▸</button>
                                  )}
                                </Td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}
    </main>
  );
}


// useParams() reads URL data, which must sit inside a Suspense boundary (cacheComponents).
export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <QuantitiesPage />
    </Suspense>
  );
}
