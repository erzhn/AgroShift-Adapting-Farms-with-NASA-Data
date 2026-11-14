"use client";

// «Откуда это число» (FR-11.1, принцип прослеживаемости 3.5): снимок данных, версия
// модели, формулы и статус каждого входа — измерено, справочник или неизвестно.

import { useEffect, useRef } from "react";

import type { ClimateCell, FieldSeason } from "../../lib/api/water";
import { formatNumber, type Lang, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  season: FieldSeason;
  cell: ClimateCell;
  lang: Lang;
  onClose: () => void;
}

export default function Provenance({ season, cell, lang, onClose }: Props) {
  const t = strings(lang);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const showValue = (value: number | string | null, unit: string | null) => {
    if (value === null) return "—";
    const text = typeof value === "number" ? formatNumber(value, lang, value % 1 ? 2 : 0)
      : value;
    return unit ? `${text} ${t.units[unit] ?? unit}` : text;
  };

  return (
    <div className={css.overlay} onClick={onClose}>
      <div className={css.dialog} role="dialog" aria-modal="true" aria-label={t.provenance}
           onClick={(event) => event.stopPropagation()}>
        <div className={css.cardHead}>
          <h2 className={css.cardTitle}>{t.provenance}</h2>
          <button ref={closeRef} type="button" className={css.button} onClick={onClose}>
            {t.provenanceClose}
          </button>
        </div>

        <p className={css.banner}>
          <span className={`${css.dot} ${season.completeness === "partial" ? css.dotWarning
            : css.dotGood}`}>{season.completeness === "partial" ? "!" : "✓"}</span>
          <span>
            {season.completeness === "partial" ? (
              <>
                <strong>{t.incomplete}:</strong>{" "}
                {season.unknown_inputs.map((u) => t.unknownInputNames[u] ?? u).join(", ")}.{" "}
                {t.incompleteHint}.
              </>
            ) : t.complete}
          </span>
        </p>

        <dl className={css.facts} style={{ marginTop: 12 }}>
          <div><dt>{t.snapshot}</dt><dd className={css.mono}>{season.snapshots.join(", ")}</dd></div>
          <div><dt>{t.modelVersion}</dt><dd>{season.model_version}</dd></div>
          <div><dt>{t.et0Method}</dt><dd>{t.et0Methods[season.et0_method]}</dd></div>
          <div><dt>{t.kcUsed}</dt><dd>{season.kc_used.map((v) => formatNumber(v, lang, 2))
            .join(" / ")}</dd></div>
          <div>
            <dt>{t.cell}</dt>
            <dd>{cell.point_name} · {formatNumber(cell.cell_elevation_m, lang)} {t.m}</dd>
          </div>
        </dl>
        <p className={css.note}>{t.resolutionNote}.</p>

        <h3>{t.formulas}</h3>
        <ul>{t.formulaList.map((line) => <li key={line}>{line}</li>)}</ul>

        <h3>{t.inputs}</h3>
        <div className={css.tableWrap}>
          <table className={`${css.table} ${css.leftCol}`}>
            <tbody>
              {Object.entries(season.inputs).map(([name, input]) => (
                <tr key={name}>
                  <td>{t.inputNames[name] ?? name}</td>
                  <td>
                    <strong>{showValue(input.value, input.unit)}</strong>
                    {input.range && (
                      <span style={{ color: "var(--text-secondary)" }}>
                        {" "}({formatNumber(input.range[0], lang, input.range[0] % 1 ? 2 : 0)}–
                        {formatNumber(input.range[1], lang, input.range[1] % 1 ? 2 : 0)})
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={css.badge} data-kind={input.source_type}>
                      {t.sourceTypes[input.source_type]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
