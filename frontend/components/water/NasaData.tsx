"use client";

// Страница «Данные NASA» (FR-11.2): наборы, дата снимка, атрибуция, ограничения
// разрешения, ячейка сетки на карте. «Используется» — только то, что реально в расчёте.

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { ApiError, type DataSources, getDataSources } from "../../lib/api/water";
import { formatDate, formatNumber, type Lang, strings, useLang } from "./strings";
import WaterNav from "./WaterNav";
import css from "./water.module.css";

// карта тяжёлая и нужна только здесь — грузим отдельно, чтобы не раздувать общий бандл
const GridCellMap = dynamic(() => import("./GridCellMap"), { ssr: false });

export default function NasaData({ lang: langProp }: { lang?: Lang }) {
  const lang = useLang(langProp);
  const t = strings(lang);
  const [data, setData] = useState<DataSources | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    getDataSources(lang, controller.signal).then(setData).catch((e: unknown) => {
      if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : t.error);
    });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, attempt]);

  const snapshots = data?.datasets.flatMap((d) => d.snapshots) ?? [];

  return (
    <main className={`${css.vizRoot} ${css.page}`}>
      <div className={css.pageInner}>
        <WaterNav lang={lang} current="nasa" />
        <header className={css.header}>
          <h1>{t.nasaTitle}</h1>
          <p className={css.lead}>{t.nasaLead}</p>
        </header>

        {error && (
          <div className={css.errorBox} role="alert">
            <span>{error}</span>
            <button type="button" className={css.button}
                    onClick={() => setAttempt((n) => n + 1)}>{t.retry}</button>
          </div>
        )}
        {!data && !error && <p className={css.message}>{t.loading}</p>}

        {data && (
          <>
            {data.offline_ready && (
              <p className={css.banner}>
                <span className={`${css.dot} ${css.dotGood}`}>✓</span>{t.offline}
              </p>
            )}

            <section className={css.card}>
              <div className={css.cardHead}>
                <div>
                  <h2 className={css.cardTitle}>{t.gridTitle}</h2>
                  <p className={css.cardSub}>{t.gridHint}</p>
                </div>
              </div>
              <GridCellMap snapshots={snapshots} lang={lang} />
            </section>

            <section className={css.card}>
              <div className={css.cardHead}>
                <div>
                  <h2 className={css.cardTitle}>{t.snapshots}</h2>
                  <p className={css.cardSub}>{t.snapshotsHint}</p>
                </div>
              </div>
              <div className={css.tableWrap}>
                <table className={css.table}>
                  <thead>
                    <tr>
                      <th>{t.point}</th>
                      <th>{t.coords}</th>
                      <th>{t.cellElevation}</th>
                      <th>{t.period}</th>
                      <th>{t.fetched}</th>
                      <th>{t.rows}</th>
                      <th>{t.missing}</th>
                      <th>{t.version}</th>
                      <th>{t.checksum}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshots.map((s) => (
                      <tr key={s.code}>
                        <td title={s.code}>{s.point_name}</td>
                        <td>{formatNumber(s.lat, lang, 2)}° / {formatNumber(s.lon, lang, 2)}°</td>
                        <td>{formatNumber(s.cell.cell_elevation_m, lang)} {t.m}</td>
                        <td>{s.period_start.slice(0, 4)}–{s.period_end.slice(0, 4)}</td>
                        <td>{formatDate(s.fetched_at, lang)}</td>
                        <td>{formatNumber(s.rows, lang)}</td>
                        <td>{s.missing_values}</td>
                        <td>{s.product_version ?? "—"}</td>
                        <td className={css.mono} title={s.sha256}>{s.sha256.slice(0, 10)}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={css.card}>
              <div className={css.cardHead}>
                <h2 className={css.cardTitle}>{t.datasets}</h2>
              </div>
              <div className={css.datasets}>
                {data.datasets.map((d) => (
                  <article key={d.id} className={css.dataset}>
                    <div className={css.datasetHead}>
                      <h3 className={css.datasetName}>
                        <a href={d.url} target="_blank" rel="noreferrer">{d.name}</a>
                      </h3>
                      <span className={css.status}>
                        <span className={`${css.dot} ${d.status === "active" ? css.dotGood
                          : css.dotMuted}`}>{d.status === "active" ? "✓" : "…"}</span>
                        {d.status === "active" ? t.used : t.planned}
                      </span>
                      <span className={css.badge}>{d.priority}</span>
                      <span className={css.cardSub}>{d.provider}</span>
                    </div>
                    <dl className={css.facts}>
                      <div><dt>{t.usedFor}</dt><dd style={{ fontWeight: 400 }}>{d.used_for}</dd></div>
                      <div><dt>{t.parameters}</dt><dd style={{ fontWeight: 400 }}>{d.parameters}</dd></div>
                      <div>
                        <dt>{t.resolution} · {t.frequency.toLowerCase()}</dt>
                        <dd style={{ fontWeight: 400 }}>{d.resolution} · {d.frequency}</dd>
                      </div>
                      <div><dt>{t.limitations}</dt><dd style={{ fontWeight: 400 }}>{d.limitations}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            <section className={css.card}>
              <div className={css.cardHead}>
                <h2 className={css.cardTitle}>{t.attribution}</h2>
              </div>
              <p className={css.attribution}>{data.attribution}</p>
              <p className={css.note}>{t.modelVersion}: {data.model_version}</p>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
