"use client";

// Точки поломки (FR-5.4): список, отсортированный по запасу прочности, с исторической
// частотой «было в N из 30 лет».

import { useEffect, useState } from "react";

import { type Breakpoint, type BreakpointsResponse, getBreakpoints } from "../../lib/api/strategies";
import type { Dict, Lang } from "./i18n";
import css from "./strategies.module.css";

interface Props {
  runId: string;
  /** названия культур по crop_id — для списка факторов, которые план выдерживает */
  names?: Record<string, string>;
  t: Dict;
  lang: Lang;
}

function factorName(factor: string, subject: string | null, name: string | null, t: Dict): string {
  const base = t.factor[factor] ?? factor;
  return subject ? `${base}: ${(name ?? subject).toLowerCase()}` : base;
}

function deltaText(b: Breakpoint, t: Dict): string {
  const sign = b.delta > 0 ? "+" : "−";
  const abs = Math.abs(b.delta);
  if (b.unit === "percent") return `${sign}${Math.round(abs)}%`;
  if (b.unit === "celsius") return `${sign}${abs.toFixed(1)} °C`;
  return `${sign}${Math.round(abs)} ${t.days}`;
}

function consequence(
  v: { violated_constraint: "cash_gap" | "yield_loss"; month: number | null; field_name: string | null },
  t: Dict,
): string {
  const what = t.breaks[v.violated_constraint];
  if (v.month) return `${what}, ${t.monthsFull[v.month - 1]}`;
  if (v.field_name) return `${what} — ${v.field_name}`;
  return what;
}

export default function BreakpointList({ runId, names = {}, t, lang }: Props) {
  const [data, setData] = useState<BreakpointsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getBreakpoints(runId, controller.signal)
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      });
    return () => controller.abort();
  }, [runId]);

  if (error) return <p className={css.error}>{t.error}: {error}</p>;
  if (!data) return <p className={css.muted}>{t.loading}</p>;
  if (data.base_violation) {
    return <p className={css.verdictBad}>{t.brokenAtBase(consequence(data.base_violation, t))}</p>;
  }

  return (
    <>
      <ol className={css.breakpoints}>
        {data.breakpoints.map((b) => {
          const name = lang === "ru" ? b.subject_name_ru : b.subject_name_en;
          const freq = b.historical_frequency;
          return (
            <li key={`${b.factor}:${b.subject ?? ""}`}>
              <span className={css.bpDelta}>{deltaText(b, t)}</span>
              <span className={css.bpFactor}>
                {factorName(b.factor, b.subject, name, t)}
                <small>→ {consequence(b, t)}</small>
              </span>
              <span className={css.bpFreq}>
                {freq ? (freq.count ? t.wasIn(freq.count, freq.of) : t.neverIn(freq.of)) : ""}
              </span>
              <span className={css.bpMargin}>
                {b.safety_margin_sigma !== null && `${t.margin} ${b.safety_margin_sigma.toFixed(1)}σ`}
              </span>
            </li>
          );
        })}
      </ol>
      {data.holds.length > 0 && (
        <p className={css.hint}>
          {t.holds}:{" "}
          {data.holds
            .map((h) => {
              const [factor, subject] = h.split(":");
              return factorName(factor, subject ?? null, names[subject ?? ""] ?? null, t);
            })
            .join(", ")}
          .
        </p>
      )}
    </>
  );
}
