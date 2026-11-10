"use client";

import { useParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import ProjectNav from "@/components/ProjectNav";
import { Button, Card, Chip, ErrorNote, FileButton, Stat, Td, Th, useAsync } from "@/components/ui";
import { api, money, qty, type CatalogRow, type CatalogView, type ProjectTakeoffItem } from "@/lib/api";

const STATUS: Record<CatalogRow["status"], { tone: "green" | "red" | "amber" | "slate"; label: string }> = {
  matches: { tone: "green", label: "Matches drawing" },
  drawing_more: { tone: "amber", label: "Drawing shows more" },
  drawing_less: { tone: "red", label: "Drawing shows less" },
  not_linked: { tone: "slate", label: "No drawing link" },
  link_missing: { tone: "red", label: "Linked item gone" },
};

const itemId = (i: { drawing_name: string; sheet: string; key?: string; takeoff_key?: string }) =>
  `${i.drawing_name}|${i.sheet}|${i.key ?? i.takeoff_key}`;

function CatalogPage() {
  const projectId = Number(useParams<{ id: string }>().id);
  const [view, setView] = useState<CatalogView | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const { busy, error, run } = useAsync();

  useEffect(() => {
    run(() => api.getCatalog(projectId).then(setView));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per project
  }, [projectId]);

  const apply = (p: Promise<CatalogView>) => run(() => p.then((v) => { setView(v); setEditing(null); }));
  const t = view?.totals;

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
      <ProjectNav projectId={projectId} />
      <ErrorNote message={error} />

      <Card
        title="Contract catalog (catálogo de conceptos)"
        actions={
          <>
            {view && view.items.length > 0 && (
              <Button onClick={() => apply(api.resuggest(projectId))} disabled={busy}>
                Re-suggest unconfirmed links
              </Button>
            )}
            <FileButton label={view?.items.length ? "Replace catalog (.xlsx)" : "Upload catalog (.xlsx)"} accept=".xlsx,.xlsm" busy={busy}
              onFile={(f) => apply(api.uploadCatalog(projectId, f))} />
          </>
        }
      >
        <p className="px-4 py-3 text-sm text-slate-600">
          Excel with columns <b>Clave, Descripción, Unidad, Cantidad, P.U.</b> (Partida optional; Spanish or English headers, any order).
          After upload, each line is linked to the drawing quantity that measures it — the system suggests a link, an engineer
          confirms or changes it. Confirmed links are what the estimación check trusts.
        </p>
      </Card>

      {view && view.items.length > 0 && t && (
        <>
          <section className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Catalog lines" value={t.items} hint={`contract total ${money(t.contract_amount)}`} />
            <Stat label="Linked to drawings" value={`${t.linked} / ${t.items}`} hint="lines with a drawing quantity" />
            <Stat label="Links confirmed" value={`${t.confirmed} / ${t.linked}`} hint="checked by an engineer" tone={t.confirmed < t.linked ? "amber" : "green"} />
            <Stat label="Contract ≠ drawing" value={t.mismatches} hint="quantities that disagree" tone={t.mismatches ? "red" : "green"} />
          </section>

          <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <Th>Clave</Th>
                  <Th>Description</Th>
                  <Th>Unit</Th>
                  <Th right>Contract qty</Th>
                  <Th right>P.U.</Th>
                  <Th>Measured by (drawing item)</Th>
                  <Th right>Drawing qty</Th>
                  <Th right>Difference</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {view.items.map((r) => (
                  <Row
                    key={r.id}
                    r={r}
                    takeoff={view.takeoff_items}
                    editing={editing === r.id}
                    busy={busy}
                    onEdit={() => setEditing(r.id)}
                    onCancel={() => setEditing(null)}
                    onSet={(it) => apply(api.setLink(r.id, { drawing_name: it.drawing_name, sheet: it.sheet, takeoff_key: it.key }))}
                    onConfirm={() => apply(api.confirmLink(r.id))}
                    onRemove={() => apply(api.removeLink(r.id))}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Difference = drawing quantity − contract quantity (in the item&apos;s unit and in pesos at the contract price). Positive means
            the drawings show more than was contracted.
          </p>
        </>
      )}
    </main>
  );
}

function Row({
  r, takeoff, editing, busy, onEdit, onCancel, onSet, onConfirm, onRemove,
}: {
  r: CatalogRow;
  takeoff: ProjectTakeoffItem[];
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSet: (it: ProjectTakeoffItem) => void;
  onConfirm: () => void;
  onRemove: () => void;
}) {
  const st = STATUS[r.status];
  const unitKind = /^(m|ml|mts?|metros?)$/i.test(r.unidad.trim()) ? "length" : "count";
  const options = useMemo(
    () => takeoff.filter((i) => i.kind === unitKind).sort((a, b) => a.drawing_name.localeCompare(b.drawing_name) || a.sheet.localeCompare(b.sheet)),
    [takeoff, unitKind],
  );
  const [choice, setChoice] = useState(r.link ? itemId(r.link) : "");

  return (
    <tr className="hover:bg-slate-50">
      <Td className="whitespace-nowrap font-medium">{r.clave}</Td>
      <Td className="min-w-[14rem] max-w-xs">{r.descripcion}</Td>
      <Td>{r.unidad}</Td>
      <Td right>{qty(r.cantidad)}</Td>
      <Td right>{money(r.precio_unitario)}</Td>
      <Td className="min-w-[16rem]">
        {editing ? (
          <div className="flex flex-col gap-2">
            <select value={choice} onChange={(e) => setChoice(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs">
              <option value="">— choose a drawing item —</option>
              {options.map((i) => (
                <option key={itemId(i)} value={itemId(i)}>
                  {i.drawing_name} · sheet {i.sheet} · {i.description} ({i.layer}) = {qty(i.quantity)} {i.unit}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <Button variant="primary" disabled={!choice || busy} onClick={() => { const it = options.find((i) => itemId(i) === choice); if (it) onSet(it); }}>
                Save link
              </Button>
              <Button onClick={onCancel}>Cancel</Button>
            </div>
          </div>
        ) : r.link ? (
          <div>
            <div className="text-xs">
              <span className="font-medium">{r.link.drawing_name}</span> · sheet {r.link.sheet} · {r.link.description ?? r.link.takeoff_key}
              <span className="text-slate-400"> ({r.link.layer})</span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {r.link.confirmed ? <Chip tone="green">Confirmed</Chip> : <Chip tone="amber">Suggested</Chip>}
              {!r.link.confirmed && <button disabled={busy} className="text-xs font-medium text-blue-700" onClick={onConfirm}>Confirm</button>}
              <button className="text-xs text-slate-500 hover:text-slate-800" onClick={onEdit}>Change</button>
              <button disabled={busy} className="text-xs text-slate-400 hover:text-red-700" onClick={onRemove}>Remove</button>
            </div>
          </div>
        ) : (
          <button className="text-xs font-medium text-blue-700" onClick={onEdit}>+ Link a drawing item</button>
        )}
      </Td>
      <Td right>{qty(r.drawing_quantity)}</Td>
      <Td right className={r.difference ? (r.difference > 0 ? "text-amber-700" : "text-red-700") : ""}>
        {r.difference === null ? "—" : (
          <>
            {r.difference > 0 ? "+" : ""}{qty(r.difference)}
            <div className="text-xs text-slate-400">{r.difference_amount ? `${r.difference_amount > 0 ? "+" : ""}${money(r.difference_amount)}` : ""}</div>
          </>
        )}
      </Td>
      <Td><Chip tone={st.tone}>{st.label}</Chip></Td>
    </tr>
  );
}


// useParams() reads URL data, which must sit inside a Suspense boundary (cacheComponents).
export default function PageWithSuspense() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">Loading…</main>}>
      <CatalogPage />
    </Suspense>
  );
}
