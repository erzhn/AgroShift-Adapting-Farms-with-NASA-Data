"use client";

// Карточки стратегий (FR-4.2) и таблица сравнения (FR-4.3).

import type { GenerateResponse, Strategy } from "../../lib/api/strategies";
import { type Dict, type Lang, decadeLabel, money, percent, volume } from "./i18n";
import css from "./strategies.module.css";

interface Props {
  data: GenerateResponse;
  selectedId: string | null;
  onSelect: (strategy: Strategy) => void;
  t: Dict;
  lang: Lang;
}

function typeTitle(s: Strategy, t: Dict): string {
  return s.types.map((kind) => t.type[kind]).join(" · ");
}

/** Диапазон P10–P90 на общей шкале всех стратегий: видно и уровень, и разброс. */
function RangeBar({ s, min, max }: { s: Strategy; min: number; max: number }) {
  const span = Math.max(1, max - min);
  const at = (v: number) => `${((v - min) / span) * 100}%`;
  const { p10, p50, p90 } = s.metrics.income_som;
  return (
    <div className={css.range} aria-hidden>
      <span className={css.rangeBand} style={{ left: at(p10), width: at(p90 - p10 + min) }} />
      <span className={css.rangeDot} style={{ left: at(p50) }} />
    </div>
  );
}

export function StrategyCards({ data, selectedId, onSelect, t, lang }: Props) {
  const all = data.strategies.map((s) => s.metrics.income_som);
  const min = Math.min(...all.map((i) => i.p10));
  const max = Math.max(...all.map((i) => i.p90));
  return (
    <div className={css.cards}>
      {data.strategies.map((s) => {
        const gap = s.metrics.cash_gap;
        const selected = s.id === selectedId;
        return (
          <button
            key={s.id}
            type="button"
            className={selected ? css.cardSelected : css.card}
            aria-pressed={selected}
            onClick={() => onSelect(s)}
          >
            <span className={css.cardType}>{typeTitle(s, t)}</span>
            <span className={css.cardSummary}>{lang === "ru" ? s.summary_ru : s.summary_en}</span>
            <span className={css.cardLabel}>{t.incomeYear}</span>
            <span className={css.cardValue}>{money(s.metrics.income_som.p50, t, lang)}</span>
            <RangeBar s={s} min={min} max={max} />
            <span className={css.cardRange}>
              {money(s.metrics.income_som.p10, t, lang)} — {money(s.metrics.income_som.p90, t, lang)}
              , {t.range}
            </span>
            <span className={gap.first_month ? css.chipBad : css.chipOk}>
              {gap.first_month ? t.gapIn(t.monthsFull[gap.first_month - 1]) : t.noGap}
              {gap.probability > 0 ? ` · ${t.gapChance(percent(gap.probability))}` : ""}
            </span>
            {s.types.length > 1 && <span className={css.chip}>{t.merged}</span>}
            {s.flags
              .filter((f) => f !== "cash_gap_risk")
              .map((f) => (
                <span key={f} className={css.chipWarn}>
                  {t.flags[f] ?? f}
                </span>
              ))}
          </button>
        );
      })}
    </div>
  );
}

export function CompareTable({ data, selectedId, onSelect, t, lang }: Props) {
  const rows: [string, (s: Strategy) => string][] = [
    [
      t.row.income,
      (s) => {
        const i = s.metrics.income_som;
        return `${money(i.p10, t, lang)} · ${money(i.p50, t, lang)} · ${money(i.p90, t, lang)}`;
      },
    ],
    [t.row.cvar, (s) => money(s.metrics.cvar10_som, t, lang)],
    [t.row.water, (s) => volume(s.metrics.gross_water_m3.p50, lang)],
    [t.row.peak, (s) => volume(s.metrics.peak_water_m3, lang)],
    [
      t.row.worst,
      (s) => {
        const w = s.metrics.worst_decade;
        return w ? `${decadeLabel(w.decade, t)} — ${volume(w.deficit_m3, lang)}` : t.none;
      },
    ],
    [
      t.row.gap,
      (s) => {
        const g = s.metrics.cash_gap;
        const when = g.first_month ? t.monthsFull[g.first_month - 1] : t.none;
        return `${when} · ${t.gapChance(percent(g.probability))}`;
      },
    ],
    [t.row.invest, (s) => money(s.metrics.investment_som, t, lang)],
    [t.row.feed, (s) => percent(s.metrics.feed_self_sufficiency)],
    [t.row.loss, (s) => percent(s.metrics.max_yield_loss)],
    [
      t.row.unsold,
      (s) =>
        s.metrics.unsold.length
          ? s.metrics.unsold.map((u) => t.unsoldT(String(u.tonnes))).join(", ")
          : t.none,
    ],
    [t.row.agro, (s) => (s.agro_status === "approved" ? t.approved : t.experimental)],
  ];
  return (
    <div className={css.tableWrap}>
      <table className={css.table}>
        <thead>
          <tr>
            <th />
            {data.strategies.map((s) => (
              <th key={s.id} className={s.id === selectedId ? css.colSelected : undefined}>
                <button type="button" className={css.colButton} onClick={() => onSelect(s)}>
                  {typeTitle(s, t)}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, cell]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              {data.strategies.map((s) => (
                <td key={s.id} className={s.id === selectedId ? css.colSelected : undefined}>
                  {cell(s)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
