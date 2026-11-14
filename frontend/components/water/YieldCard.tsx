"use client";

// Урожай P10/P50/P90 и потеря от дефицита по стадиям (FR-3.3).
// Простой режим ТЗ (12.4): «в плохой / обычный / хороший год» вместо процентилей.
// Урожай — модельная оценка, показывается с диапазоном и не точнее 0,1 т/га.

import type { Ensemble, FieldSeason } from "../../lib/api/water";
import { formatNumber, type Lang, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  season: FieldSeason;
  ensemble: Ensemble;
  lang: Lang;
  onProvenance: () => void;
}

export default function YieldCard({ season, ensemble, lang, onProvenance }: Props) {
  const t = strings(lang);
  const inTonnes = ensemble.yield_t_ha !== null && season.yield_t_ha !== null;
  const range = inTonnes ? ensemble.yield_t_ha! : {
    p10: ensemble.yield_multiplier.p10 * 100, p50: ensemble.yield_multiplier.p50 * 100,
    p90: ensemble.yield_multiplier.p90 * 100,
  };
  const unit = inTonnes ? t.yieldUnit : `% ${t.ofPotential}`;
  const digits = inTonnes ? 1 : 0;
  const show = (v: number) => formatNumber(v, lang, digits);

  const losses = season.stages.map((s) => ({ stage: s.stage, loss: (1 - s.factor) * 100 }));
  const worst = Math.max(...losses.map((l) => l.loss));
  const scale = Math.max(worst, 10);

  return (
    <section className={css.card}>
      <div className={css.cardHead}>
        <div>
          <h2 className={css.cardTitle}>{t.yieldTitle}</h2>
          <p className={css.cardSub}>
            {t.modelEstimate} · {ensemble.years.length} {t.nasaYears}
          </p>
        </div>
        <button type="button" className={css.infoButton} onClick={onProvenance}>
          {t.provenance}
        </button>
      </div>

      <p className={css.hero}>
        <span className={css.heroValue}>{show(range.p50)}</span>
        <span className={css.heroUnit}>{unit} · {t.usualYear}</span>
      </p>

      <dl className={css.range}>
        <div><dt>{t.badYear}</dt><dd>{show(range.p10)}</dd></div>
        <div><dt>{t.usualYear}</dt><dd>{show(range.p50)}</dd></div>
        <div><dt>{t.goodYear}</dt><dd>{show(range.p90)}</dd></div>
      </dl>

      <p className={css.note}>
        {t.thisYear(season.year)}:{" "}
        <strong>
          {inTonnes ? `${show(season.yield_t_ha!)} ${t.yieldUnit} · ` : ""}
          {formatNumber(season.yield_multiplier * 100, lang)} % {t.ofPotential}
        </strong>
      </p>

      <h3 className={css.cardTitle} style={{ fontSize: 15, marginTop: 16 }}>{t.lossByStage}</h3>
      <ul className={css.meters}>
        {losses.map((l) => {
          const isMax = worst >= 1 && l.loss === worst;
          return (
            <li key={l.stage} className={css.meterRow}>
              <span>
                {t.stageNames[l.stage]}
                {isMax && <span className={css.tag}>{t.mostImportant}</span>}
              </span>
              <span className={css.meterTrack} aria-hidden="true">
                <span className={css.meterFill} data-max={isMax}
                      style={{ display: "block", width: `${Math.min(l.loss / scale, 1) * 100}%` }} />
              </span>
              <span className={css.meterValue}>
                {l.loss < 0.5 ? "0 %" : `−${formatNumber(l.loss, lang)} %`}
              </span>
            </li>
          );
        })}
        {season.f_heat < 1 && (
          <li className={css.meterRow}>
            <span>{t.heatLoss}</span><span />
            <span className={css.meterValue}>
              −{formatNumber((1 - season.f_heat) * 100, lang)} %
            </span>
          </li>
        )}
        {season.f_frost < 1 && (
          <li className={css.meterRow}>
            <span>{t.frostLoss}</span><span />
            <span className={css.meterValue}>
              −{formatNumber((1 - season.f_frost) * 100, lang)} %
            </span>
          </li>
        )}
      </ul>
    </section>
  );
}
