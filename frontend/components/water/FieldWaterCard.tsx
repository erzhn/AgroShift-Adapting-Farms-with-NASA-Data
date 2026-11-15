"use client";

// Карточка поля (раздел 9.3 ТЗ): паспорт (FR-3.1), график сезона и истощение почвы
// (FR-3.2), урожай P10/P50/P90 с потерями по стадиям (FR-3.3), «откуда это число».

import { useEffect, useState } from "react";

import { ApiError, getWaterBalance, type WaterBalance } from "../../lib/api/water";
import Provenance from "./Provenance";
import WaterNav from "./WaterNav";
import SeasonChart from "./SeasonChart";
import SoilChart from "./SoilChart";
import { decadeLabel, formatDate, formatNumber, type Lang, strings, useLang } from "./strings";
import css from "./water.module.css";
import YieldCard from "./YieldCard";

interface Props {
  fieldId: string;
  strategy?: string;
  scenario?: string;
  lang?: Lang;
}

export default function FieldWaterCard({ fieldId, strategy, scenario, lang: langProp }: Props) {
  const lang = useLang(langProp);
  const t = strings(lang);
  const [data, setData] = useState<WaterBalance | null>(null);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError(null);
    getWaterBalance(fieldId, { strategy, scenario, year, daily: true }, controller.signal)
      .then((result) => { setData(result); setBusy(false); })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof ApiError ? e.message : t.error);
        setBusy(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldId, strategy, scenario, year, attempt]);

  if (!data) {
    return (
      <main className={`${css.vizRoot} ${css.page}`}>
        <div className={css.pageInner}>
          {error ? (
            <div className={css.errorBox} role="alert">
              <span>{error}</span>
              <button type="button" className={css.button}
                      onClick={() => setAttempt((n) => n + 1)}>{t.retry}</button>
            </div>
          ) : <p className={css.message}>{t.loading}</p>}
        </div>
      </main>
    );
  }

  const { field, season, ensemble, cell } = data;
  const worst = season.decades.find((d) => d.decade === season.worst_decade);
  const worstHistory = ensemble.decades.find((d) => d.decade === season.worst_decade);
  const otherAlerts = season.alerts.filter((a) => a.type !== "water_deficit");

  return (
    <main className={`${css.vizRoot} ${css.page}`} aria-busy={busy}>
      <div className={css.pageInner}>
        <WaterNav lang={lang} farmId={field.source === "farms" ? field.farm_id : null} />
        <header className={css.header}>
          <h1>{field.name} · {field.crop_name}</h1>
          <p className={css.lead}>
            {field.farm_name ? `${field.farm_name} · ` : ""}{t.resolutionNote}
          </p>
        </header>

        {/* фильтры — одной строкой над всем, что они охватывают */}
        <div className={css.filters}>
          <label>
            {t.year}
            <select className={css.select} value={year ?? ""}
                    onChange={(e) => setYear(e.target.value ? Number(e.target.value)
                      : undefined)}>
              <option value="">{t.typicalYear} ({year === undefined ? data.year : "…"})</option>
              {[...ensemble.years].reverse().map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
          {year === undefined && <span className={css.cardSub}>{t.typicalYearHint}</span>}
        </div>

        {error && (
          <div className={css.errorBox} role="alert">
            <span>{error}</span>
            <button type="button" className={css.button}
                    onClick={() => setAttempt((n) => n + 1)}>{t.retry}</button>
          </div>
        )}
        {field.source === "demo" && (
          <p className={css.banner}>
            <span className={`${css.dot} ${css.dotMuted}`}>i</span>{t.demoProfile}
          </p>
        )}

        <div className={css.grid2}>
          <section className={css.card}>
            <div className={css.cardHead}><h2 className={css.cardTitle}>{t.passport}</h2></div>
            <dl className={css.facts}>
              <div><dt>{t.area}</dt><dd>{formatNumber(field.area_ha, lang, 2)} {t.ha}</dd></div>
              <div><dt>{t.crop}</dt><dd>{field.crop_name}</dd></div>
              <div><dt>{t.sowing}</dt><dd>{formatDate(season.sowing_date, lang, false)}</dd></div>
              <div>
                <dt>{t.elevation}</dt>
                <dd>{field.elevation_m === null ? t.unknown
                  : `${formatNumber(field.elevation_m, lang)} ${t.m}`}</dd>
              </div>
              <div>
                <dt>{t.soil}</dt>
                <dd>{field.soil_type ? t.soils[field.soil_type] ?? field.soil_type
                  : t.unknown}</dd>
              </div>
              <div>
                <dt>{t.irrigation}</dt>
                <dd>{t.irrigationMethods[field.irrigation_method] ?? field.irrigation_method}</dd>
              </div>
            </dl>

            <h3 className={css.cardTitle} style={{ fontSize: 15, marginTop: 16 }}>{t.totals}</h3>
            <dl className={css.facts} style={{ marginTop: 8 }}>
              <div>
                <dt>{t.needGross}</dt>
                <dd>{formatNumber(season.totals.need_gross_m3, lang)} {t.m3}</dd>
              </div>
              <div>
                <dt>{t.gotByTurn}</dt>
                <dd>{formatNumber(season.totals.received_m3, lang)} {t.m3}</dd>
              </div>
              <div>
                <dt>{t.deficit}</dt>
                <dd>{formatNumber(season.totals.deficit_m3, lang)} {t.m3} ·{" "}
                  {formatNumber(season.totals.deficit_pct, lang)} %</dd>
              </div>
            </dl>

            {season.totals.received_m3 >= season.totals.need_gross_m3
              && season.totals.deficit_pct >= 5 && <p className={css.note}>{t.timingNote}</p>}
            {worst && (
              <p className={css.note}>
                <span className={css.status}>
                  <span className={`${css.dot} ${css.dotCritical}`}>!</span>
                  <strong>{t.worstDecade}: {decadeLabel(worst.decade, lang)}</strong>
                </span>
                {" — "}{t.deficit.toLowerCase()} {formatNumber(worst.deficit_pct, lang)} %
                {worstHistory && worstHistory.years_deficit_ge20 > 0
                  ? `, ${t.yearsOf(worstHistory.years_deficit_ge20, ensemble.years.length)}`
                  : ""}
              </p>
            )}
            {otherAlerts.length > 0 && (
              <ul className={css.alerts}>
                {otherAlerts.map((a) => (
                  <li key={a.type} className={css.status}>
                    <span className={`${css.dot} ${css.dotWarning}`}>!</span>
                    {t.alerts[a.type]}
                    {a.decade ? ` · ${decadeLabel(a.decade, lang)}` : ""}
                    {a.days ? ` · ${a.days} ${t.days}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <YieldCard season={season} ensemble={ensemble} lang={lang}
                     onProvenance={() => setShowProvenance(true)} />
        </div>

        <SeasonChart season={season} lang={lang} busy={busy} />
        {season.daily && <SoilChart daily={season.daily} lang={lang} busy={busy} />}
      </div>

      {showProvenance && (
        <Provenance season={season} cell={cell} lang={lang}
                    onClose={() => setShowProvenance(false)} />
      )}
    </main>
  );
}
