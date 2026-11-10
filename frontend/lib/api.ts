export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Project = {
  id: number;
  name: string;
  client: string | null;
  location: string | null;
  contract_number: string | null;
  contractor: string | null;
  scope: string | null;
  supervisor_name: string | null;
  supervisor_title: string | null;
  approver_name: string | null;
  approver_title: string | null;
  created_at: string;
};

export type ProjectDetails = Partial<Omit<Project, "id" | "created_at">>;

export type Readiness = { ready: boolean; missing: string[]; problems: string[] };

export type BidEvaluation = {
  budget_total: number;
  recommended: string | null;
  recommendation_note: string;
  bidders: {
    bidder: string;
    bid_id: number;
    source_filename: string;
    total: number;
    vs_budget: number;
    vs_budget_pct: number | null;
    missing_items: string[];
    extra_items: string[];
    price_outliers: string[];
    complete: boolean;
    rank: number;
  }[];
  items: {
    clave: string;
    descripcion: string;
    unidad: string;
    cantidad: number;
    budget_unit_price: number;
    median_unit_price: number | null;
    bidders: Record<string, { unit_price: number | null; amount: number | null; flag: "missing" | "high" | "low" | null }>;
  }[];
};

export type FieldView = {
  entries: { id: number; fecha: string; clave: string; cantidad: number; zona: string | null; nota: string | null; reportado_por: string | null; in_catalog: boolean }[];
  progress: { clave: string; descripcion: string; unidad: string; contract: number; installed: number; percent: number | null }[];
};

export type DrawingVersion = {
  id: number;
  version: number;
  original_filename: string;
  file_format: "dwg" | "dxf";
  sha256: string;
  size_bytes: number;
  status: "pending" | "ready" | "failed";
  error: string | null;
  reader: string | null;
  cad_version: string | null;
  object_count: number | null;
  layer_count: number | null;
  symbol_count: number | null;
  label_count: number | null;
  uploaded_at: string;
};

export type DrawingVersionDetail = DrawingVersion & {
  drawing_id: number;
  drawing_name: string;
  project_id: number;
  total_versions: number;
};

export type Drawing = { id: number; name: string; versions: DrawingVersion[] };

export type UploadResult = { drawing: string; version: DrawingVersion; duplicate: boolean };

export type Analysis = {
  source_format: string;
  dwg_version: string;
  reader: string;
  units: string;
  totals: {
    objects: number;
    layers: number;
    symbols_placed: number;
    symbol_types: number;
    labels: number;
    unique_labels: number;
  };
  object_types: Record<string, number>;
  layers: {
    name: string;
    objects: number;
    length: number;
    labels: number;
    symbol_count: number;
    symbols: { name: string; count: number }[];
  }[];
  symbols: {
    name: string;
    count: number;
    anonymous: boolean;
    layers: { name: string; count: number }[];
    attribs: { value: string; count: number }[];
  }[];
  labels: { text: string; count: number; layers: string[] }[];
  notes: string[];
};

export type TakeoffItem = {
  key: string;
  sheet: string;
  kind: "count" | "length";
  description: string;
  symbol: string | null;
  layer: string;
  unit: string;
  quantity: number;
  method: string;
  zones: Record<string, number>;
};

export type ProjectTakeoffItem = TakeoffItem & { drawing_name: string; version_id: number; version: number };

export type DrawingTakeoff = {
  drawing_id: number;
  drawing_name: string;
  version_id: number;
  version: number;
  sheets: { id: string; box: number[] | null }[];
  zones: string[];
  legend_boxes: number;
  excluded: Record<string, number>;
  rules: Record<string, string>;
  items: TakeoffItem[];
};

export type CatalogRow = {
  id: number;
  clave: string;
  descripcion: string;
  unidad: string;
  cantidad: number;
  precio_unitario: number;
  importe: number;
  partida: string | null;
  link: {
    drawing_name: string;
    sheet: string;
    takeoff_key: string;
    confirmed: boolean;
    score: number;
    description: string | null;
    layer: string | null;
    method: string | null;
  } | null;
  drawing_quantity: number | null;
  difference: number | null;
  difference_amount: number | null;
  status: "not_linked" | "link_missing" | "matches" | "drawing_more" | "drawing_less";
};

export type CatalogView = {
  items: CatalogRow[];
  takeoff_items: ProjectTakeoffItem[];
  totals: { items: number; contract_amount: number; linked: number; confirmed: number; mismatches: number };
};

export type Finding = { code: string; severity: "error" | "warning" | "info"; message: string };

export type EstimacionLineResult = {
  id: number;
  row: number;
  clave: string;
  descripcion: string;
  unidad: string;
  contract_unit_price: number | null;
  claimed_unit_price: number | null;
  claimed: number;
  previous_approved: number;
  cumulative: number;
  contract_quantity: number | null;
  drawing_quantity: number | null;
  approvable: number;
  claimed_amount: number;
  approvable_amount: number;
  severity: "ok" | "info" | "warning" | "error";
  result: string;
  findings: Finding[];
};

export type EstimacionTotals = {
  lines: number;
  claimed_amount: number;
  approvable_amount: number;
  errors: number;
  warnings: number;
  not_verified: number;
  ok: number;
};

export type EstimacionSummary = {
  id: number;
  numero: number;
  periodo: string | null;
  source_filename: string;
  status: "checked" | "approved";
  uploaded_at: string;
  approved_at: string | null;
  totals: EstimacionTotals;
};

export type EstimacionResult = EstimacionSummary & { lines: EstimacionLineResult[] };

export type QuantityChange = {
  sheet: string;
  key: string;
  description: string;
  layer: string;
  unit: string;
  old: number;
  new: number;
  delta: number;
  status: "added" | "removed" | "changed";
  catalog_clave: string | null;
  unit_price: number | null;
  cost_impact: number | null;
};

export type Comparison = {
  drawing_name: string;
  old: { id: number; version: number; filename: string; uploaded_at: string };
  new: { id: number; version: number; filename: string; uploaded_at: string };
  quantity_changes: QuantityChange[];
  cost_impact_total: number;
  unpriced_changes: number;
  objects: { old: number; new: number };
  labels_added: string[];
  labels_removed: string[];
  layers_added: string[];
  layers_removed: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Cannot reach the backend at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function upload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  return request<T>(path, { method: "POST", body: form });
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; dwg_reader: string; dxf_reader: string }>("/health"),
  listProjects: () => request<Project[]>("/projects"),
  createProject: (data: { name: string; client?: string; location?: string }) =>
    request<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  listDrawings: (projectId: number) => request<Drawing[]>(`/projects/${projectId}/drawings`),
  uploadDrawing: (projectId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResult>(`/projects/${projectId}/drawings`, { method: "POST", body: form });
  },
  getVersion: (versionId: number) => request<DrawingVersionDetail>(`/drawing-versions/${versionId}`),
  getAnalysis: (versionId: number) => request<Analysis>(`/drawing-versions/${versionId}/analysis`),
  previewUrl: (versionId: number) => `${API_URL}/drawing-versions/${versionId}/preview.svg`,
  getProject: (projectId: number) => request<Project>(`/projects/${projectId}`),
  getTakeoff: (versionId: number) => request<Omit<DrawingTakeoff, "drawing_id" | "drawing_name" | "version_id" | "version">>(`/drawing-versions/${versionId}/takeoff`),
  getTakeoffSummary: (projectId: number) => request<DrawingTakeoff[]>(`/projects/${projectId}/takeoff-summary`),
  compare: (drawingId: number, oldV: number, newV: number) =>
    request<Comparison>(`/drawings/${drawingId}/compare?old=${oldV}&new=${newV}`),

  getCatalog: (projectId: number) => request<CatalogView>(`/projects/${projectId}/catalog`),
  uploadCatalog: (projectId: number, file: File) => upload<CatalogView>(`/projects/${projectId}/catalog`, file),
  resuggest: (projectId: number) => request<CatalogView>(`/projects/${projectId}/catalog/suggest`, json("POST")),
  setLink: (itemId: number, link: { drawing_name: string; sheet: string; takeoff_key: string }) =>
    request<CatalogView>(`/catalog-items/${itemId}/link`, json("PUT", { ...link, confirmed: true })),
  confirmLink: (itemId: number) => request<CatalogView>(`/catalog-items/${itemId}/confirm`, json("POST")),
  removeLink: (itemId: number) => request<CatalogView>(`/catalog-items/${itemId}/link`, json("DELETE")),

  listEstimaciones: (projectId: number) => request<EstimacionSummary[]>(`/projects/${projectId}/estimaciones`),
  uploadEstimacion: (projectId: number, file: File, numero: number, periodo: string) =>
    upload<EstimacionResult>(`/projects/${projectId}/estimaciones`, file, { numero: String(numero), periodo }),
  getEstimacion: (id: number) => request<EstimacionResult>(`/estimaciones/${id}`),
  approveEstimacion: (id: number) => request<EstimacionResult>(`/estimaciones/${id}/approve`, json("POST")),
  deleteEstimacion: (id: number) => request<void>(`/estimaciones/${id}`, json("DELETE")),
  exportUrl: (id: number) => `${API_URL}/estimaciones/${id}/export.xlsx`,

  updateProject: (projectId: number, data: ProjectDetails) => request<Project>(`/projects/${projectId}`, json("PUT", data)),
  readiness: (projectId: number) => request<Readiness>(`/projects/${projectId}/report-readiness`),
  dictamenUrl: (estId: number) => `${API_URL}/estimaciones/${estId}/dictamen.pdf`,

  getBids: (projectId: number) => request<BidEvaluation>(`/projects/${projectId}/bids`),
  uploadBid: (projectId: number, file: File, bidder: string) => upload<BidEvaluation>(`/projects/${projectId}/bids`, file, { bidder }),
  deleteBid: (bidId: number) => request<BidEvaluation>(`/bids/${bidId}`, json("DELETE")),
  bidsReportUrl: (projectId: number) => `${API_URL}/projects/${projectId}/bids/report.pdf`,

  getField: (projectId: number) => request<FieldView>(`/projects/${projectId}/field`),
  addField: (projectId: number, entry: { fecha: string; clave: string; cantidad: number; zona?: string; nota?: string; reportado_por?: string }) =>
    request<FieldView>(`/projects/${projectId}/field`, json("POST", entry)),
  uploadField: (projectId: number, file: File) => upload<FieldView>(`/projects/${projectId}/field/upload`, file),
  deleteField: (entryId: number) => request<FieldView>(`/field-entries/${entryId}`, json("DELETE")),
  fieldReportUrl: (projectId: number) => `${API_URL}/projects/${projectId}/field/report.pdf`,
};

/** Download a generated report; shows the server's reason (e.g. missing project details) instead of a broken file. */
export async function downloadReport(url: string, filename: string) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `Report failed (${res.status})`);
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const money = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const qty = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 2 });

const PROJECT_KEY = "inpros:lastProject";
export const rememberProject = (id: number) => {
  try {
    localStorage.setItem(PROJECT_KEY, String(id));
  } catch {
    /* storage unavailable: fine */
  }
};
export const lastProject = (): number | null => {
  try {
    const v = Number(localStorage.getItem(PROJECT_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
};
