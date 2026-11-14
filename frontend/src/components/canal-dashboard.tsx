"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "@/src/i18n";
import type { Geometry, Point } from "geojson";
import DemandChart from "@/src/components/demand-chart";
import { buildCanalChartData } from "@/src/lib/canal-chart";

const CanalMap = dynamic(() => import("@/src/components/canal-map"), { ssr: false });
const API_ROOT = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API = `${API_ROOT.replace(/\/$/, "")}${API_ROOT.endsWith("/api/v1") ? "" : "/api/v1"}`;

type Geo = Geometry | null;
type Canal = {
  id: string;
  name: string;
  invite_code: string | null;
  conveyance_efficiency: number;
  geometry: Geo;
  snow_catchment_geometry: Geo;
};
type SupplyRow = { decade: number; volume_m3: number | null; source_type: string; reliability: number };
type FarmMapRow = {
  farm_id: string;
  farm_name: string;
  field_id: string;
  field_name: string;
  area_ha: number;
  location: Point | null;
  geometry: Geo;
  crop_code: string | null;
  crop_name: string | null;
  sowing_date: string | null;
};
type DemandDecade = {
  decade: number;
  supply_head_m3: number;
  demand_head_before_m3: number;
  demand_head_after_m3: number;
  deficit_before_m3: number;
  deficit_after_m3: number;
};
type CropDemandDecade = { decade: number; crops: Record<string, number> };
type Demand = {
  status?: string;
  plan_id?: string;
  plan_status?: string;
  farm_count?: number;
  peak_deficit_before_m3?: number;
  peak_deficit_after_m3?: number;
  coordination_gain_percent?: number;
  coordination_useful?: boolean;
  fairness_satisfied?: boolean;
  message?: string | null;
  decades: DemandDecade[];
  crop_demand_head_m3_by_decade?: CropDemandDecade[];
};
type Proposal = {
  id: string;
  farm_id: string;
  change: {
    farm_name: string;
    kind: string;
    shift_days: number;
    sowing_date_before: string;
    sowing_date_after: string;
  };
  water_delta_m3: number;
  response: string;
};
type Plan = { id: string; status: string; proposals: Proposal[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function formatM3(value: number | undefined): string {
  return typeof value === "number" ? `${Math.round(value).toLocaleString()} м³` : "—";
}

export default function CanalDashboard() {
  const { t, i18n } = useTranslation();
  const [canals, setCanals] = useState<Canal[]>([]);
  const [canalId, setCanalId] = useState("");
  const [season, setSeason] = useState(2027);
  const [supply, setSupply] = useState<SupplyRow[]>([]);
  const [farms, setFarms] = useState<FarmMapRow[]>([]);
  const [demand, setDemand] = useState<Demand>({ decades: [] });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadCanals = useCallback(async () => {
    const items = await request<Canal[]>("/canals");
    setCanals(items);
    const demoCanal = items.find((item) => item.invite_code === "AGROSHIFT-DEMO");
    setCanalId((current) => current || demoCanal?.id || items[0]?.id || "");
  }, []);

  useEffect(() => {
    void loadCanals().catch((exception: Error) => setError(exception.message));
  }, [loadCanals]);

  const reload = useCallback(async () => {
    if (!canalId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [supplyRows, farmRows, demandResult] = await Promise.all([
        request<SupplyRow[]>(`/canals/${canalId}/supply?season=${season}`),
        request<FarmMapRow[]>(`/canals/${canalId}/farms?season=${season}`),
        request<Demand>(`/canals/${canalId}/demand?season=${season}`),
      ]);
      setSupply(supplyRows);
      setFarms(farmRows);
      setDemand(demandResult);
      if (demandResult.plan_id) {
        setPlan(await request<Plan>(`/canal-plans/${demandResult.plan_id}`));
      } else {
        setPlan(null);
      }
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : t("failed"));
    } finally {
      setLoading(false);
    }
  }, [canalId, season, t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const supplyByDecade = useMemo(
    () => new Map(supply.map((row) => [row.decade, row])),
    [supply],
  );
  const chartData = useMemo(
    () => buildCanalChartData(demand.decades ?? [], supply),
    [demand.decades, supply],
  );

  const cropTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const decade of demand.crop_demand_head_m3_by_decade ?? []) {
      for (const [code, value] of Object.entries(decade.crops)) {
        totals[code] = (totals[code] ?? 0) + value;
      }
    }
    return Object.entries(totals).sort((left, right) => right[1] - left[1]);
  }, [demand.crop_demand_head_m3_by_decade]);

  const selectedCanal = canals.find((item) => item.id === canalId) ?? null;

  async function createDemoCanal() {
    setBusy(true);
    setError("");
    try {
      const canal = await request<Canal>("/canals", {
        method: "POST",
        body: JSON.stringify({
          name: "Демо-канал AgroShift",
          avp_name: "Демо АВП",
          conveyance_efficiency: 0.5,
          geometry: {
            type: "MultiLineString",
            coordinates: [[[74.56, 42.83], [74.61, 42.87], [74.66, 42.9]]],
          },
          snow_catchment_geometry: {
            type: "MultiPolygon",
            coordinates: [[[[74.48, 42.78], [74.72, 42.78], [74.72, 42.98],
              [74.48, 42.98], [74.48, 42.78]]]],
          },
        }),
      });
      setCanals((current) => [...current, canal]);
      setCanalId(canal.id);
      setNotice(t("createDemo"));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : t("failed"));
    } finally {
      setBusy(false);
    }
  }

  async function saveSupply() {
    if (!canalId) return;
    if (Array.from({ length: 36 }, (_, index) => supplyByDecade.get(index + 1)).some((row) => row?.volume_m3 == null)) {
      setError(t("supplyIncomplete"));
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const rows = Array.from({ length: 36 }, (_, index) => {
        const current = supplyByDecade.get(index + 1);
        return {
          decade: index + 1,
          volume_m3: current!.volume_m3 as number,
          source_type: current?.source_type ?? "user_estimate",
          reliability: current?.reliability ?? 0.8,
        };
      });
      const saved = await request<SupplyRow[]>(`/canals/${canalId}/supply`, {
        method: "PUT",
        body: JSON.stringify({ season, decades: rows }),
      });
      setSupply(saved);
      setNotice(t("saved"));
      await reload();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : t("failed"));
    } finally {
      setBusy(false);
    }
  }

  async function coordinatePlan() {
    if (!canalId) return;
    const rows = Array.from({ length: 36 }, (_, index) => supplyByDecade.get(index + 1));
    if (rows.some((row) => row?.volume_m3 == null)) {
      setError(t("supplyIncomplete"));
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request<SupplyRow[]>(`/canals/${canalId}/supply`, {
        method: "PUT",
        body: JSON.stringify({
          season,
          decades: rows.map((row, index) => ({
            decade: index + 1,
            volume_m3: row!.volume_m3,
            source_type: row!.source_type,
            reliability: row!.reliability,
          })),
        }),
      });
      const created = await request<Plan>(`/canals/${canalId}/coordinate`, {
        method: "POST",
        body: JSON.stringify({ season }),
      });
      setPlan(created);
      setNotice(t("planCalculated"));
      await reload();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : t("failed"));
    } finally {
      setBusy(false);
    }
  }

  async function respondToProposal(proposalId: string, response: "agree" | "reject") {
    setBusy(true);
    setError("");
    try {
      await request(`/canal-proposals/${proposalId}:respond`, {
        method: "POST",
        body: JSON.stringify({ response }),
      });
      await reload();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : t("failed"));
    } finally {
      setBusy(false);
    }
  }

  function updateSupply(decade: number, value: number | null) {
    setSupply((current) => {
      const next = [...current];
      const index = next.findIndex((row) => row.decade === decade);
      const row: SupplyRow = { decade, volume_m3: value, source_type: "user_estimate", reliability: 0.8 };
      if (index >= 0) next[index] = { ...next[index], volume_m3: value };
      else next.push(row);
      return next.sort((left, right) => left.decade - right.decade);
    });
  }

  function updateSupplyMeta(
    decade: number,
    patch: Partial<Pick<SupplyRow, "reliability" | "source_type">>,
  ) {
    setSupply((current) => {
      const next = [...current];
      const index = next.findIndex((row) => row.decade === decade);
      const row: SupplyRow = {
        decade,
        volume_m3: null,
        source_type: "user_estimate",
        reliability: 0.8,
        ...(index >= 0 ? next[index] : {}),
        ...patch,
      };
      if (index >= 0) next[index] = row;
      else next.push(row);
      return next.sort((left, right) => left.decade - right.decade);
    });
  }

  return (
    <main className="app-shell canal-root">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="AgroShift home">
          <span className="brand-mark">A</span>
          <span>AgroShift</span>
        </a>
        <div className="side-label">WORKSPACE</div>
        <nav className="workspace-nav" aria-label={t("workspace")}>
          <a className="nav-item" href="/">
            <span className="nav-glyph" aria-hidden="true">←</span>
            {i18n.language.startsWith("en") ? "Farm dashboard" : "К хозяйству"}
          </a>
        </nav>
        <div className="side-bottom">
          <div className="role-card">
            <span className="role-avatar">А</span>
            <span><b>Демо АВП</b><small>Чуйская область</small></span>
            <span className="online-dot" />
          </div>
          <span className="version-label">AGROSHIFT · MVP 0.1</span>
        </div>
      </aside>

      <section className="main-area" id="top">
        <header className="topbar">
          <div className="breadcrumbs"><span>AgroShift</span><i>/</i><b>Кабинет АВП</b></div>
          <div className="top-actions">
            <label className="language-control" aria-label={t("language")}>
              <span>◎</span>
              <select value={i18n.language.startsWith("en") ? "en" : "ru"}
                onChange={(event) => void i18n.changeLanguage(event.target.value)}>
                <option value="ru">RU</option><option value="en">EN</option>
              </select>
            </label>
            <button className="icon-button" aria-label="Уведомления">♧<span className="notification-dot" /></button>
            <span className="user-badge">Ж</span>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-dot" /> WATER COORDINATION</div>
              <h1>{t("title")}</h1>
              <p>{t("subtitle")}</p>
            </div>
            <div className="heading-controls">
              <label className="select-field">
                <span>{t("canal")}</span>
                <select value={canalId} onChange={(event) => setCanalId(event.target.value)} disabled={!canals.length}>
                  {canals.map((canal) => <option key={canal.id} value={canal.id}>{canal.name}</option>)}
                </select>
              </label>
              <label className="select-field year-field">
                <span>{t("season")}</span>
                <select value={season} onChange={(event) => setSeason(Number(event.target.value))}>
                  {[2027].map((year) => <option key={year}>{year}</option>)}
                </select>
              </label>
            </div>
          </div>

          {error && <div className="notice error-notice" role="alert">{error}</div>}
          {notice && <div className="notice success-notice" role="status">{notice}</div>}

          {!canals.length && !loading ? (
            <section className="empty-state panel">
              <span className="empty-icon">⌁</span>
              <h2>{t("noCanals")}</h2>
              <p>Создайте канал, затем загрузите хозяйства и график подачи.</p>
              <button className="primary-button" onClick={() => void createDemoCanal()} disabled={busy}>
                {t("createDemo")}
              </button>
            </section>
          ) : (
            <>
              <div className="metric-grid">
                <article className="metric-card">
                  <div className="metric-top"><span className="metric-icon mint">⌂</span><span className="metric-context">{t("season")} {season}</span></div>
                  <span className="metric-label">{t("farms")}</span>
                  <strong>{loading ? "—" : demand.farm_count ?? farms.length}</strong>
                  <span className="metric-foot">{selectedCanal?.name ?? t("unknown")}</span>
                </article>
                <article className="metric-card">
                  <div className="metric-top"><span className="metric-icon amber">⌁</span><span className="metric-context">36 {t("decade").toLowerCase()}</span></div>
                  <span className="metric-label">{t("waterPeak")}</span>
                  <strong>{formatM3(demand.peak_deficit_after_m3 ?? demand.peak_deficit_before_m3)}</strong>
                  <span className="metric-foot">{demand.status === "not_calculated" ? t("noPlan") : t("after")}</span>
                </article>
                <article className="metric-card">
                  <div className="metric-top"><span className="metric-icon blue">↗</span><span className="metric-context">{demand.coordination_gain_percent?.toFixed(1) ?? "0.0"}%</span></div>
                  <span className="metric-label">{t("waterGain")}</span>
                  <strong>{formatM3((demand.peak_deficit_before_m3 ?? 0) - (demand.peak_deficit_after_m3 ?? 0))}</strong>
                  <span className="metric-foot">{t("before")} → {t("after")}</span>
                </article>
                <article className="metric-card trust-card">
                  <div className="metric-top"><span className="metric-icon violet">◌</span><span className="metric-context">{t("status")}</span></div>
                  <span className="metric-label">{t("planStatus") || "План канала"}</span>
                  <strong className="status-strong">{demand.plan_status ? t(demand.plan_status) : t("unknown")}</strong>
                  <span className="metric-foot">{t("sources")}</span>
                </article>
              </div>

              <div className="content-grid">
                <section className="panel chart-panel">
                  <div className="panel-heading">
                    <div><h2>{t("demandChart")}</h2><p>м³ на голове канала · 36 декад</p></div>
                    <span className="quiet-pill">{selectedCanal ? `${Math.round(selectedCanal.conveyance_efficiency * 100)}% КПД` : "—"}</span>
                  </div>
                  {demand.message && (
                    <div className={`inline-note ${demand.fairness_satisfied === false ? "warning-note" : ""}`}>
                      <span>ⓘ</span>{demand.fairness_satisfied === false ? t("fairnessBlocked") : t("lowBenefit")}
                    </div>
                  )}
                  <DemandChart data={chartData} loading={loading} />
                  <div className="chart-legend-note"><span className="legend-swatch" /> {t("sources")}</div>
                </section>

                <section className="panel map-panel">
                  <div className="panel-heading">
                    <div><h2>{t("farmsMap")}</h2><p>{farms.length} {t("farms").toLowerCase()}</p></div>
                    <button className="quiet-icon" onClick={() => void reload()} aria-label="Обновить">↻</button>
                  </div>
                  <CanalMap canal={selectedCanal} farms={farms} />
                  <div className="map-foot"><span><i className="map-dot farm-dot" /> {t("farms")}</span><span><i className="map-dot canal-dot" /> {t("canal")}</span><b>{selectedCanal?.invite_code ?? ""}</b></div>
                </section>
              </div>

              <div className="lower-grid">
                <section className="panel supply-panel">
                  <div className="panel-heading">
                    <div><h2>{t("supply")}</h2><p>Объём на голове канала · источник и надёжность</p></div>
                    <button className="primary-button small-button" onClick={() => void saveSupply()} disabled={busy || !canalId}>
                      {busy ? t("loading") : t("saveSupply")}
                    </button>
                  </div>
                  <div className="supply-table-wrap">
                    <table className="supply-table">
                      <thead><tr><th>{t("decade")}</th><th>{t("amount")}</th><th>{t("reliability")}</th><th>Источник</th></tr></thead>
                      <tbody>
                        {Array.from({ length: 36 }, (_, index) => {
                          const decade = index + 1;
                          const row = supplyByDecade.get(decade);
                          return <tr key={decade}>
                            <td><span className="decade-index">{String(decade).padStart(2, "0")}</span><span className="decade-period">{Math.floor(index / 3) + 1} / {index % 3 + 1}</span></td>
                            <td><input aria-label={`${t("amount")} ${decade}`} type="number" min="0" step="100" value={row?.volume_m3 ?? ""} placeholder="—" onChange={(event) => updateSupply(decade, event.target.value === "" ? null : Math.max(0, Number(event.target.value)))} /></td>
                            <td><input className="reliability-input" aria-label={`${t("reliability")} ${decade}`} type="number" min="0" max="1" step="0.05" value={row?.reliability ?? 0.8} onChange={(event) => updateSupplyMeta(decade, { reliability: Math.max(0, Math.min(1, Number(event.target.value))) })} /></td>
                            <td><select className="source-select" aria-label={`Источник ${decade}`} value={row?.source_type ?? "user_estimate"} onChange={(event) => updateSupplyMeta(decade, { source_type: event.target.value })}><option value="user_estimate">оценка</option><option value="measured">измерено</option><option value="model">модель</option><option value="reference">справочник</option><option value="satellite">спутник</option><option value="unknown">неизвестно</option></select></td>
                          </tr>;
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="panel side-stack">
                  <div className="panel-heading">
                    <div><h2>Спрос по культурам</h2><p>Суммарно за сезон, брутто</p></div>
                    <span className="quiet-pill">{cropTotals.length} культур</span>
                  </div>
                  {cropTotals.length ? (
                    <div className="crop-list">
                      {cropTotals.map(([code, amount], index) => (
                        <div className="crop-row" key={code}>
                          <span className={`crop-badge crop-${index % 4}`}>{code.slice(0, 2).toUpperCase()}</span>
                          <span className="crop-name">{code}</span>
                          <strong>{formatM3(amount)}</strong>
                        </div>
                      ))}
                    </div>
                  ) : <div className="small-empty">{t("noPlan")}</div>}
                  <div className="coordination-callout">
                    <div className="callout-symbol">✳</div>
                    <div><b>План координации</b><p>{t("noHydrology")}</p></div>
                    <button className="primary-button small-button" onClick={() => void coordinatePlan()} disabled={busy || !canalId}>
                      {busy ? t("loading") : t("calculatePlan")}
                    </button>
                  </div>
                </section>
              </div>

              <section className="panel proposals-panel">
                <div className="panel-heading">
                  <div><h2>{t("proposals")}</h2><p>Индивидуальные изменения и подача воды без финансовых данных других хозяйств</p></div>
                  <span className="quiet-pill">{plan?.proposals.length ?? 0} предложений</span>
                </div>
                {plan?.proposals.length ? (
                  <div className="proposal-table-wrap">
                    <table className="proposal-table">
                      <thead><tr><th>Хозяйство</th><th>{t("change")}</th><th>{t("waterChange")}</th><th>{t("status")}</th></tr></thead>
                      <tbody>{plan.proposals.map((proposal) => <tr key={proposal.id}>
                        <td><span className="farm-avatar">{proposal.change.farm_name.slice(0, 1)}</span><b>{proposal.change.farm_name}</b></td>
                        <td>{proposal.change.shift_days ? `${t("shift")} ${proposal.change.shift_days > 0 ? "+" : ""}${proposal.change.shift_days} дн.` : t("noShift")}</td>
                        <td className={proposal.water_delta_m3 >= 0 ? "positive-value" : "negative-value"}>{proposal.water_delta_m3 >= 0 ? "+" : ""}{Math.round(proposal.water_delta_m3).toLocaleString()} м³</td>
                        <td>
                          <span className={`status-chip ${proposal.response}`}>{t(proposal.response) || proposal.response}</span>
                          {proposal.response === "pending" && (
                            <div className="proposal-actions">
                              <button type="button" disabled={busy} onClick={() => void respondToProposal(proposal.id, "agree")}>{t("agreeAction")}</button>
                              <button type="button" disabled={busy} onClick={() => void respondToProposal(proposal.id, "reject")}>{t("rejectAction")}</button>
                            </div>
                          )}
                        </td>
                      </tr>)}</tbody>
                    </table>
                  </div>
                ) : <div className="small-empty">{t("noPlan")}</div>}
              </section>
              <footer className="page-footer"><span>AgroShift · NASA Space Apps Challenge</span><span>Данные канала · сезон {season}</span></footer>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
