// Клиент API модуля «Вода и климат». Типы повторяют backend/app/modules/water/schemas.py.
// Единицы: вода — мм и м³ (1 мм на 1 га = 10 м³), даты — ISO, декады — индекс 1..36.

// relative by default: Next rewrites /api/* to the backend (next.config.ts)
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const BASE = `${API_URL}/api/v1`;

export type StageName = "ini" | "dev" | "mid" | "late";
export type DecadeStatus = "ok" | "deficit_lt20" | "deficit_ge20";
export type SourceType =
  | "measured" | "satellite" | "model" | "reference" | "user_estimate" | "unknown";

export interface Percentiles { p10: number; p50: number; p90: number }

export interface InputValue {
  value: number | string | null;
  unit: string | null;
  source_type: SourceType;
  range: [number, number] | null;
}

export interface DecadeWater {
  decade: number;
  start: string;
  end: string;
  days: number;
  stage: StageName;
  et0_mm: number;
  etc_mm: number;
  eta_mm: number;
  precip_mm: number;
  eff_precip_mm: number;
  runoff_mm: number;
  deep_percolation_mm: number;
  irrigation_net_mm: number;
  need_net_mm: number;
  need_gross_m3: number;
  gross_mm: number;
  need_head_m3: number;
  received_m3: number;
  used_m3: number;
  deficit_mm: number;
  deficit_m3: number;
  deficit_pct: number;
  stress_pct: number;
  ks_avg: number;
  dr_end_mm: number;
  raw_mm: number;
  taw_mm: number;
  turns_planned: number;
  turns_failed: number;
  hot_days: number;
  status: DecadeStatus;
}

export interface StageYield {
  stage: StageName;
  days: number;
  etc_mm: number;
  eta_mm: number;
  ratio: number;
  ky: number;
  factor: number;
}

export interface Alert {
  type: "water_deficit" | "frost_in_bloom" | "heat_in_flowering" | "resow_risk";
  decade: number | null;
  days: number | null;
  value: number | null;
}

export interface DailySeries {
  dates: string[];
  et0: number[];
  etc: number[];
  eta: number[];
  precip: number[];
  irrigation: number[];
  dr: number[];
  raw: number[];
  taw: number[];
  ks: number[];
}

export interface SeasonTotals {
  et0_mm: number;
  etc_mm: number;
  eta_mm: number;
  precip_mm: number;
  eff_precip_mm: number;
  irrigation_net_mm: number;
  need_net_mm: number;
  need_gross_m3: number;
  gross_mm: number;
  need_head_m3: number;
  received_m3: number;
  used_m3: number;
  deficit_m3: number;
  deficit_pct: number;
}

export interface FieldSeason {
  field_id: string;
  crop_code: string;
  year: number;
  sowing_date: string;
  harvest_date: string;
  season_days: number;
  stage_days: [number, number, number, number];
  area_ha: number;
  decades: DecadeWater[];
  stages: StageYield[];
  totals: SeasonTotals;
  worst_decade: number | null;
  yield_multiplier: number;
  f_water: number;
  f_heat: number;
  f_frost: number;
  yield_potential_t_ha: number | null;
  yield_t_ha: number | null;
  yield_status: "model_estimate";
  alerts: Alert[];
  balance_error_mm: number;
  completeness: "complete" | "partial";
  unknown_inputs: string[];
  inputs: Record<string, InputValue>;
  snapshots: string[];
  model_version: string;
  et0_method: "penman_monteith" | "mixed" | "hargreaves";
  kc_used: [number, number, number];
  daily: DailySeries | null;
}

export interface EnsembleDecade {
  decade: number;
  need_gross_m3: Percentiles;
  received_m3: Percentiles;
  deficit_pct: Percentiles;
  years_deficit_ge20: number;
}

export interface Ensemble {
  years: number[];
  yield_multiplier: Percentiles;
  yield_t_ha: Percentiles | null;
  need_gross_m3: Percentiles;
  deficit_m3: Percentiles;
  decades: EnsembleDecade[];
  per_year: { year: number; yield_multiplier: number; deficit_m3: number;
              worst_decade: number | null }[];
}

export interface ClimateCell {
  snapshot: string;
  point_name: string | null;
  center: [number, number];
  bbox: [number, number, number, number];
  cell_elevation_m: number;
  resolution_note_key: string;
}

export interface FieldInfo {
  id: string;
  name: string;
  farm_id: string | null;
  farm_name: string | null;
  area_ha: number;
  lat: number | null;
  lon: number | null;
  elevation_m: number | null;
  soil_type: string | null;
  irrigation_method: string;
  crop_code: string;
  crop_name: string;
  sowing_date: string;
  source: "farms" | "demo";
}

export interface WaterBalance {
  field: FieldInfo;
  cell: ClimateCell;
  strategy: string | null;
  scenario: string | null;
  year: number;
  year_mode: "requested" | "scenario" | "median";
  season: FieldSeason;
  ensemble: Ensemble;
}

export interface SnapshotInfo {
  code: string;
  point_name: string | null;
  lat: number;
  lon: number;
  cell: ClimateCell;
  period_start: string;
  period_end: string;
  fetched_at: string;
  rows: number;
  sha256: string;
  product_version: string | null;
  missing_values: number;
}

export interface Dataset {
  id: string;
  name: string;
  provider: string;
  parameters: string;
  resolution: string;
  frequency: string;
  used_for: string;
  limitations: string;
  priority: string;
  status: "active" | "planned";
  url: string;
  snapshots: SnapshotInfo[];
}

export interface DataSources {
  attribution: string;
  model_version: string;
  offline_ready: boolean;
  datasets: Dataset[];
}

export interface ClimateDay {
  date: string;
  tmax: number;
  tmin: number;
  tmean: number;
  precip: number;
  rs: number;
  ws2m: number;
  rh_min: number;
  et0: number;
  et0_method: "pm" | "hs";
}

export interface FieldClimate {
  field_id: string;
  cell: ClimateCell;
  date_from: string;
  date_to: string;
  field_elevation_m: number | null;
  temperature_shift_c: number;
  et0_method: string;
  days: ClimateDay[];
  decade_norms: { decade: number; et0_mm: Percentiles; precip_mm: Percentiles;
                  tmean_c: Percentiles; hot_days_mean: number }[];
  frost: { year: number; last_spring_frost: string | null;
           first_autumn_frost: string | null }[];
  history_years: number[];
  qc: { days: number; missing: number; out_of_range: number; interpolated: number;
        filled_with_norm: number };
  model_version: string;
  attribution: string;
}

export class ApiError extends Error {
  constructor(public status: number, public title: string, public detail?: string) {
    super(detail ?? title);
  }
}

async function get<T>(path: string, params: Record<string, unknown> = {},
                      signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const qs = query.toString();
  const response = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`, { signal });
  if (!response.ok) {
    // ошибки API — RFC 9457 (application/problem+json)
    const problem = await response.json().catch(() => ({}));
    throw new ApiError(response.status, problem.title ?? response.statusText, problem.detail);
  }
  return response.json() as Promise<T>;
}

export interface WaterBalanceOptions {
  strategy?: string;
  scenario?: string;
  year?: number;
  daily?: boolean;
}

export function getWaterBalance(fieldId: string, options: WaterBalanceOptions = {},
                                signal?: AbortSignal): Promise<WaterBalance> {
  return get(`/fields/${encodeURIComponent(fieldId)}/water-balance`, { ...options }, signal);
}

export function getFieldClimate(fieldId: string, from?: string, to?: string,
                                signal?: AbortSignal): Promise<FieldClimate> {
  return get(`/fields/${encodeURIComponent(fieldId)}/climate`, { from, to }, signal);
}

export function getDataSources(lang = "ru", signal?: AbortSignal): Promise<DataSources> {
  return get("/data-sources", { lang }, signal);
}
