"use client";

import { useRef, useState } from "react";

export function Card({ title, actions, children }: { title?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        </div>
      )}
      <div>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "red" | "amber" | "green" }) {
  const color = tone === "red" ? "text-red-700" : tone === "amber" ? "text-amber-700" : tone === "green" ? "text-green-700" : "";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

const CHIP = {
  green: "bg-green-50 text-green-700",
  red: "bg-red-50 text-red-700",
  amber: "bg-amber-50 text-amber-800",
  blue: "bg-blue-50 text-blue-700",
  slate: "bg-slate-100 text-slate-600",
} as const;

export function Chip({ tone, children, title }: { tone: keyof typeof CHIP; children: React.ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${CHIP[tone]}`}>
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "secondary",
  disabled,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const style =
    variant === "primary"
      ? "bg-blue-600 text-white hover:bg-blue-700"
      : variant === "danger"
        ? "border border-red-200 text-red-700 hover:bg-red-50"
        : "border border-slate-300 hover:bg-slate-50";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${style}`}>
      {children}
    </button>
  );
}

/** Small file picker button for one Excel file. */
export function FileButton({ label, accept, onFile, busy }: { label: string; accept: string; onFile: (f: File) => void; busy?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button variant="primary" onClick={() => input.current?.click()} disabled={busy}>
        {busy ? "Working…" : label}
      </Button>
      <input
        ref={input}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </>
  );
}

export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{message}</p>;
}

export function useAsync() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}

export function Th({ children, right }: { children?: React.ReactNode; right?: boolean }) {
  return <th className={`whitespace-nowrap px-3 py-2 font-medium ${right ? "text-right" : "text-left"}`}>{children}</th>;
}

export function Td({ children, right, className = "" }: { children?: React.ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-3 py-2 align-top ${right ? "text-right tabular-nums" : ""} ${className}`}>{children}</td>;
}
