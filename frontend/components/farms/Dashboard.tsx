"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type Crop,
  type Farm,
  type FarmWrite,
  type Field,
  type FieldWrite,
  type Language,
  type Rotation,
  type Scenario,
} from "@/lib/api/farms";
import { colors, cropName, planYear, seasonFor, stageFor, countUnit } from "@/lib/farms";
import { locales, messages, monthNames, type Translate } from "@/lib/i18n";
import Catalog from "./Catalog";
import FieldForm from "./FieldForm";
import Icon from "./Icon";
import Modal from "./Modal";
import PlanningLanes, { type FarmIntegrations } from "./PlanningLanes";
import ProfileForm from "./ProfileForm";
import MoneyIntegration from "./MoneyIntegration";
import WaterIntegration from "./WaterIntegration";
import useFarmStrategies from "./useFarmStrategies";
import { previewFields } from "@/lib/planning";
import { readPreference, writePreference } from "@/lib/preferences";

const FarmMap = dynamic(() => import("./FarmMap"), {
  ssr: false,
  loading: () => <div className="map-frame skeleton" />,
});
const DEFAULT_INTEGRATIONS: FarmIntegrations = {};

export default function Dashboard({
  integrations = DEFAULT_INTEGRATIONS,
}: {
  integrations?: FarmIntegrations;
}) {
  const [language, setLanguage] = useState<Language>("ru");
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [tab, setTab] = useState<"farm" | "catalog">("farm");
  const [farms, setFarms] = useState<Farm[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [presets, setPresets] = useState<Scenario[]>([]);
  const [rotations, setRotations] = useState<Rotation[]>([]);
  const [farmId, setFarmId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [year, setYear] = useState(2027);
  const [month, setMonth] = useState(7);
  const [scenarioId, setScenarioId] = useState("");
  const [strategyId, setStrategyId] = useState("current");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [profile, setProfile] = useState<"edit" | "new" | null>(null);
  const [editor, setEditor] = useState<Field | "new" | null>(null);
  const [deleting, setDeleting] = useState<{ kind: "farm" | "field"; id: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const createKey = useRef("");
  const t: Translate = (key) => messages[language][key];
  const farm = farms.find((f) => f.id === farmId);
  const scenario = presets.find((s) => s.id === scenarioId) || null;
  const planning = useFarmStrategies(farm, year, scenario);
  const chosenStrategy = planning.data?.strategies.find((s) =>
    strategyId === "current" ? s.types.includes("user") : s.id === strategyId,
  );
  const displayFields = previewFields(farm?.fields || [], crops, chosenStrategy, year);
  const field = displayFields.find((f) => f.id === selected);
  const activeIntegrations: FarmIntegrations = {
    ...integrations,
    WaterLane: integrations.WaterLane || WaterIntegration,
    MoneyLane: integrations.MoneyLane || (chosenStrategy ? MoneyIntegration : undefined),
  };
  const months = monthNames(language);
  const number = (value: number | null, digits = 0) =>
    value === null
      ? "—"
      : value.toLocaleString(locales[language], { maximumFractionDigits: digits });
  const strategies = [
    { id: "current", name: t("currentPlan") },
    ...(planning.data?.strategies
      .filter((s) => !s.types.includes("user"))
      .map((s) => ({
        id: s.id,
        name: s.types.map((type) => t(type === "user" ? "currentPlan" : type)).join(" / "),
      })) || []),
    ...(integrations.strategies || []).filter((s) => s.id !== "current"),
  ];

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [farmList, cropList, scenarioList, rotationList] = await Promise.all([
        api.farms(),
        api.crops(),
        api.scenarios(),
        api.rotations(),
      ]);
      setFarms(farmList);
      setCrops(cropList);
      setPresets(scenarioList);
      setRotations(rotationList);
      const remembered = readPreference("agroshift-farm");
      // demo: without a remembered farm open the richest one (Асан, 3 fields)
      const richest = [...farmList].sort((a, b) => b.fields.length - a.fields.length)[0];
      const first = farmList.find((f) => f.id === remembered) || richest;
      setFarmId(first?.id || "");
      setSelected(first?.fields[0]?.id || null);
      if (first) setYear(planYear(first.fields));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    const saved = readPreference("agroshift.lang") || readPreference("agroshift-language");
    if (saved === "ru" || saved === "en" || saved === "ky") setLanguage(saved);
    setPreferencesLoaded(true);
  }, [load]);
  useEffect(() => {
    if (!preferencesLoaded) return;
    document.documentElement.lang = language;
    writePreference("agroshift-language", language);
    writePreference("agroshift.lang", language);
    window.dispatchEvent(new Event("agroshift:lang"));
  }, [language, preferencesLoaded]);
  useEffect(() => {
    setStrategyId("current");
  }, [farm, scenarioId, year]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  function chooseFarm(id: string) {
    const chosen = farms.find((f) => f.id === id);
    setFarmId(id);
    setSelected(chosen?.fields[0]?.id || null);
    if (chosen) setYear(planYear(chosen.fields));
    setStrategyId("current");
    setScenarioId("");
    writePreference("agroshift-farm", id);
  }
  function updateFarm(next: Farm) {
    setFarms((current) =>
      current.some((f) => f.id === next.id)
        ? current.map((f) => (f.id === next.id ? next : f))
        : [...current, next],
    );
  }
  function openProfile(mode: "edit" | "new") {
    createKey.current = crypto.randomUUID();
    setProfile(mode);
  }
  function openField(value: Field | "new") {
    createKey.current = crypto.randomUUID();
    setEditor(value);
  }
  async function saveProfile(data: FarmWrite) {
    const next =
      profile === "new"
        ? await api.createFarm(data, createKey.current)
        : await api.updateFarm(farmId, data);
    updateFarm(next);
    setFarmId(next.id);
    writePreference("agroshift-farm", next.id);
    if (profile === "new") {
      setSelected(null);
      setYear(2027);
    }
    setToast(t(profile === "new" ? "created" : "saved"));
    setProfile(null);
  }
  async function saveField(data: FieldWrite) {
    const next =
      editor === "new"
        ? await api.createField(farmId, data, createKey.current)
        : await api.updateField(farmId, (editor as Field).id, data);
    updateFarm(await api.farm(farmId));
    setSelected(next.id);
    setEditor(null);
    setToast(t("fieldsSaved"));
  }
  function confirmDelete(kind: "field" | "farm", id: string) {
    setProfile(null);
    setEditor(null);
    setDeleteError("");
    setDeleting({ kind, id });
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError("");
    try {
      if (deleting.kind === "farm") {
        await api.deleteFarm(deleting.id);
        const left = farms.filter((f) => f.id !== deleting.id);
        setFarms(left);
        setFarmId(left[0]?.id || "");
        setSelected(left[0]?.fields[0]?.id || null);
      } else {
        await api.deleteField(farmId, deleting.id);
        const next = await api.farm(farmId);
        updateFarm(next);
        setSelected(next.fields[0]?.id || null);
      }
      setDeleting(null);
      setToast(t("deleted"));
    } catch (err) {
      setDeleteError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const cows =
    farm?.herds
      .filter((h) => h.species === "cow" && h.purpose === "milk")
      .reduce((n, h) => n + h.head_count, 0) ?? 0;
  const crop = crops.find((c) => c.id === (field && seasonFor(field, year)?.crop_id));
  const startYear = farm ? planYear(farm.fields) : 2027;
  const years = Array.from(
    new Set([
      year,
      ...Array.from({ length: 5 }, (_, i) => startYear + i),
      ...(farm?.fields.flatMap((f) => f.seasons.map((s) => s.year)) || []),
    ]),
  ).sort();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="AgroShift">
          <span className="brand-symbol">
            <Icon name="leaf" size={28} />
          </span>
          <span>
            Agro<span className="brand-light">Shift</span>
            <small>{t("tagline")}</small>
          </span>
        </a>
        <div className="sidebar-label">{t("workspace")}</div>
        <nav aria-label={t("workspace")}>
          <button
            className={tab === "farm" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("farm")}
          >
            <Icon name="grid" />
            {t("home")}
            <span className="nav-dot" />
          </button>
          <button
            className={tab === "catalog" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("catalog")}
          >
            <Icon name="book" />
            {t("catalog")}
          </button>
          <button className="nav-item" disabled={!farm} onClick={() => openProfile("edit")}>
            <Icon name="edit" />
            {t("settings")}
          </button>
          <a className="nav-item" href="/canal">
            <Icon name="drop" />
            Кабинет АВП
          </a>
          <a className="nav-item" href="/nasa">
            <Icon name="leaf" />
            NASA
          </a>
        </nav>
        <div className="sidebar-season">
          <Icon name="leaf" size={26} />
          <strong>
            {t("season")} {year}
          </strong>
          <span>{t("sourceHint")}</span>
          <div className="season-line">
            <i />
          </div>
        </div>
        <div className="sidebar-bottom">
          <div className="nasa-word">
            NASA <span>SPACE APPS</span>
          </div>
          <p>
            AgroShift · 2026
            <br />
            Bishkek, Kyrgyzstan
          </p>
          <span className="version-tag">DEMO</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>{t("workspace")}</span>
            <Icon name="chevron" size={13} />
            <strong>{t(tab === "farm" ? "home" : "catalog")}</strong>
          </div>
          <div className="topbar-actions">
            <div className="language-switch" aria-label="Language">
              {(["ru", "ky", "en"] as Language[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLanguage(l)}
                  aria-pressed={language === l}
                  className={language === l ? "selected" : ""}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
            <span className="avatar">{farm?.name?.slice(0, 1) || "A"}</span>
          </div>
        </header>
        <main id="main-content">
          {loading ? (
            <div className="loading-state" role="status">
              <div className="spinner" />
              <p>{t("loading")}</p>
            </div>
          ) : error ? (
            <div className="empty-state" role="alert">
              <Icon name="info" size={40} />
              <h1>{t("error")}</h1>
              <p>{error}</p>
              <button className="button primary" onClick={load}>
                {t("retry")}
              </button>
            </div>
          ) : tab === "catalog" ? (
            <Catalog crops={crops} rotations={rotations} language={language} t={t} />
          ) : !farm ? (
            <div className="empty-state">
              <Icon name="leaf" size={44} />
              <h1>{t("noFarms")}</h1>
              <p>{t("noFarmsHint")}</p>
              <button className="button primary" onClick={() => openProfile("new")}>
                <Icon name="plus" />
                {t("addFarm")}
              </button>
            </div>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="live-dot" />
                    {t("season")} {year} <span className="eyebrow-divider">/</span>{" "}
                    {farm.district || "Кыргызстан"}
                  </div>
                  <h1>{t("title")}</h1>
                  <p>{t("subtitle")}</p>
                </div>
                <button
                  className="button secondary profile-button"
                  onClick={() => openProfile("edit")}
                >
                  <Icon name="edit" size={17} />
                  {t("profile")}
                </button>
              </div>
              <div className="farm-toolbar">
                <div className="farm-switch">
                  <span className="farm-monogram">{farm.name.slice(0, 1)}</span>
                  <label className="sr-only" htmlFor="farm-switch">
                    {t("wholeFarm")}
                  </label>
                  <select
                    id="farm-switch"
                    value={farmId}
                    onChange={(e) => chooseFarm(e.target.value)}
                  >
                    {farms.map((f) => (
                      <option value={f.id} key={f.id}>
                        {f.name} · {f.village || f.district || "—"}
                      </option>
                    ))}
                  </select>
                  <button
                    className="icon-button"
                    onClick={() => openProfile("new")}
                    aria-label={t("addFarm")}
                  >
                    <Icon name="plus" size={18} />
                  </button>
                </div>
                <div className="plan-selects">
                  <label>
                    {t("strategy")}
                    <select
                      value={strategyId}
                      onChange={(e) => setStrategyId(e.target.value)}
                      title={strategies.length === 1 ? t("planOnly") : undefined}
                    >
                      {strategies.map((s) => (
                        <option value={s.id} key={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t("scenario")}
                    <select value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
                      <option value="">{t("baseScenario")}</option>
                      {presets.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.preset_code in messages[language]
                            ? t(s.preset_code as "like_2023")
                            : s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
              {(planning.loading || planning.error || planning.historical || planning.data) && (
                <div className="scenario-note planning-status" role="status">
                  <Icon name="info" size={16} />
                  <span>
                    {planning.historical
                      ? t("historicalPending")
                      : planning.loading
                        ? t("calculating")
                        : planning.error || t("calculationEstimate")}
                    {chosenStrategy && !chosenStrategy.types.includes("user") && (
                      <> {t("previewHint")}</>
                    )}
                  </span>
                  <a href={`/strategies?farm=${encodeURIComponent(farm.id)}`}>
                    {t("compareStrategies")} ↗
                  </a>
                </div>
              )}
              <div className="stats-grid">
                {(
                  [
                    ["field", t("area"), number(farm.area_ha, 2), t("ha")],
                    [
                      "map",
                      t("fields"),
                      number(farm.fields.length),
                      countUnit(farm.fields.length, language, "fields"),
                    ],
                    [
                      "cow",
                      t("cows"),
                      farm.herds.length ? number(cows) : "—",
                      countUnit(cows, language, "cows"),
                    ],
                    ["wallet", t("cash"), number(farm.cash_som), t("som")],
                  ] as const
                ).map(([icon, label, value, unit]) => (
                  <div className="stat" key={icon}>
                    <span className={`stat-icon stat-${icon}`}>
                      <Icon name={icon} size={22} />
                    </span>
                    <div>
                      <span className="stat-label">{label}</span>
                      <strong>
                        {value}
                        <small>{unit}</small>
                      </strong>
                    </div>
                  </div>
                ))}
              </div>
              <section className="map-panel">
                <div className="section-heading">
                  <div>
                    <h2>{t("map")}</h2>
                    <p>{t("mapHint")}</p>
                  </div>
                  <button className="button primary" onClick={() => openField("new")}>
                    <Icon name="plus" size={18} />
                    {t("addField")}
                  </button>
                </div>
                <div className="map-layout">
                  <div className="fields-list">
                    <div className="list-title">
                      {t("fieldList")}
                      <span>{farm.fields.length}</span>
                    </div>
                    {!farm.fields.length && (
                      <div className="field-empty">
                        <Icon name="field" size={30} />
                        <strong>{t("noFields")}</strong>
                        <p>{t("noFieldsHint")}</p>
                      </div>
                    )}
                    {displayFields.map((f, i) => {
                      const season = seasonFor(f, year);
                      const c = crops.find((c) => c.id === season?.crop_id);
                      const stage = stageFor(season, month, year);
                      return (
                        <button
                          key={f.id}
                          className={`field-card ${f.id === selected ? "selected" : ""}`}
                          aria-pressed={f.id === selected}
                          onClick={() => setSelected(f.id)}
                        >
                          <span className="field-number">{String(i + 1).padStart(2, "0")}</span>
                          <div>
                            <strong>{f.name}</strong>
                            <span className="crop-label">
                              <i style={{ background: colors[c?.code || ""] || "#8d9893" }} />
                              {cropName(c, language)}
                              <span>
                                · {number(f.area_ha, 2)} {t("ha")}
                              </span>
                            </span>
                            <span className={`stage-pill stage-${stage}`}>{t(stage)}</span>
                          </div>
                          <Icon name="chevron" size={15} />
                        </button>
                      );
                    })}
                    <button className="catalog-link" onClick={() => setTab("catalog")}>
                      {t("viewCatalog")}
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                  <FarmMap
                    fields={displayFields}
                    crops={crops}
                    year={year}
                    selected={selected}
                    onSelect={setSelected}
                    t={t}
                    language={language}
                  />
                </div>
                {field && (
                  <div className="field-detail">
                    <span
                      className="field-detail-symbol"
                      style={{ color: colors[crop?.code || ""] }}
                    >
                      <Icon name="leaf" size={24} />
                    </span>
                    <div>
                      <strong>{field.name}</strong>
                      <span>
                        {cropName(crop, language)} · {number(field.area_ha, 2)} {t("ha")} ·{" "}
                        {t(field.irrigation_method as "furrow")}
                      </span>
                    </div>
                    <div className="field-dates">
                      <span>
                        {t("sowingDate")}
                        <strong>{seasonFor(field, year)?.sowing_date || "—"}</strong>
                      </span>
                      <span>
                        {t("harvestDate")}
                        <strong>{seasonFor(field, year)?.harvest_date || "—"}</strong>
                      </span>
                    </div>
                    <a
                      className="button secondary small"
                      href={`/field/${encodeURIComponent(field.id)}?${new URLSearchParams({
                        lang: language,
                        ...(strategyId !== "current" && chosenStrategy
                          ? { strategy: chosenStrategy.run_id }
                          : {}),
                        ...(scenario ? { scenario: scenario.preset_code } : {}),
                      })}`}
                    >
                      <Icon name="drop" size={15} />
                      {t("water")}
                    </a>
                    <button
                      className="button secondary small"
                      onClick={() => openField(farm.fields.find((f) => f.id === field.id)!)}
                    >
                      <Icon name="edit" size={15} />
                      {t("edit")}
                    </button>
                  </div>
                )}
              </section>
              <section className="timeline-panel">
                <div className="section-heading">
                  <div className="heading-inline">
                    <Icon name="calendar" size={20} />
                    <h2>{t("timeline")}</h2>
                  </div>
                  <label className="year-switch">
                    <span>{t("year")}</span>
                    <select
                      aria-label={t("year")}
                      value={year}
                      onChange={(e) => setYear(Number(e.target.value))}
                    >
                      {years.map((y) => (
                        <option key={y}>{y}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="months" role="group" aria-label={t("month")}>
                  {months.map((name, i) => (
                    <button
                      key={i}
                      className={month === i + 1 ? "active" : ""}
                      aria-pressed={month === i + 1}
                      onClick={() => setMonth(i + 1)}
                    >
                      <span>{String(i + 1).padStart(2, "0")}</span>
                      {name.replace(".", "")}
                    </button>
                  ))}
                </div>
                <div className="timeline-caption">
                  <span>
                    <i className="calendar-dot" />
                    {t("monthHint")}
                  </span>
                  <strong>
                    {months[month - 1]} {year}
                  </strong>
                </div>
                {farm.fields.length > 0 && !farm.fields.some((f) => seasonFor(f, year)) && (
                  <p className="year-empty">{t("seasonMissing")}</p>
                )}
              </section>
              <PlanningLanes
                context={{
                  farm,
                  year,
                  month,
                  strategyId,
                  scenario,
                  runId: chosenStrategy?.run_id,
                  language,
                  onMonthChange: setMonth,
                }}
                integrations={activeIntegrations}
                t={t}
              />
              <footer className="workspace-footer">
                <Icon name="info" size={16} />
                <span>
                  <strong>{t("demo")}</strong> {t("demoHint")}
                </span>
                <span className="footer-wordmark">AgroShift</span>
              </footer>
            </>
          )}
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" size={18} />
          {toast}
        </div>
      )}
      {profile && (
        <ProfileForm
          farm={profile === "edit" ? farm : undefined}
          t={t}
          onSave={saveProfile}
          onClose={() => setProfile(null)}
          onDelete={profile === "edit" && farm ? () => confirmDelete("farm", farm.id) : undefined}
        />
      )}
      {editor && farm && (
        <FieldForm
          field={editor === "new" ? undefined : editor}
          crops={crops}
          year={year}
          language={language}
          t={t}
          onSave={saveField}
          onClose={() => setEditor(null)}
          onDelete={editor !== "new" ? () => confirmDelete("field", editor.id) : undefined}
        />
      )}
      {deleting && (
        <Modal
          title={t(deleting.kind === "farm" ? "deleteFarm" : "deleteField")}
          closeLabel={t("close")}
          onClose={() => !busy && setDeleting(null)}
        >
          <div className="modal-body">
            <p>{t("deleteHint")}</p>
            {deleteError && (
              <p className="form-error" role="alert">
                {deleteError}
              </p>
            )}
          </div>
          <div className="modal-footer">
            <button className="button secondary" disabled={busy} onClick={() => setDeleting(null)}>
              {t("cancel")}
            </button>
            <button className="button danger" disabled={busy} onClick={remove}>
              {t("deleteConfirm")}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
