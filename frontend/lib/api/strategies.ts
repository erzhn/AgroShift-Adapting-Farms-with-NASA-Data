// Клиент API модуля «Стратегии и деньги» (владелец — Абдулазис).
// Типы повторяют backend/app/schemas/strategies.py. Деньги — целые сомы, вода — м³,
// декады — 1–36, месяцы — 1–12.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export type StrategyType = "income" | "resilient" | "water_light" | "user";

export interface Percentiles {
  p10: number;
  p50: number;
  p90: number;
}

export interface Scenario {
  water_supply_factor: number; // 0.5…1.2; 0.8 = −20%
  supply_shift_days: number; // −30…30, + позже
  temp_delta_c: number; // 0…3
  precip_factor: number; // 0.5…1.3
  water_months: number[]; // к каким месяцам относится множитель подачи; [] — весь сезон
  price_factor: number; // 0.5…1.5
  price_factors: Record<string, number>;
  feed_price_factor: number; // 0.5…1.5
  payment_delay_days: number; // 0…120, дополнительная задержка
  yield_factor: number; // 0.7…1.3
}

export const BASE_SCENARIO: Scenario = {
  water_supply_factor: 1,
  supply_shift_days: 0,
  temp_delta_c: 0,
  precip_factor: 1,
  water_months: [],
  price_factor: 1,
  price_factors: {},
  feed_price_factor: 1,
  payment_delay_days: 0,
  yield_factor: 1,
};

export interface Decision {
  field_id: string;
  field_name: string;
  crop_id: string;
  crop_name_ru: string;
  crop_name_en: string;
  area_ha: number;
  action: "keep" | "switch" | "uproot_and_sow";
  capex_som: number;
}

export interface WorstDecade {
  decade: number;
  deficit_m3: number;
  field_id: string | null;
  field_name: string | null;
}

export interface Unsold {
  crop_id: string;
  tonnes: number;
  max_volume_t: number;
}

export interface CashGap {
  first_month: number | null;
  worst_month: number | null;
  depth_som: number;
  financing_needed_som: number;
  probability: number;
}

export interface Financing {
  amount_som: number; // сколько привлечь; по плохим годам
  month: number | null; // 1–12, к какому месяцу нужны деньги
  p_gap_limit: number; // с этой суммой разрыв не чаще этой доли лет
}

export interface StrategyMetrics {
  income_som: Percentiles;
  cvar10_som: number;
  gross_water_m3: Percentiles;
  peak_water_m3: number;
  worst_decade: WorstDecade | null;
  cash_gap: CashGap;
  investment_som: number;
  feed_self_sufficiency: number;
  feed_purchase_som: number;
  max_yield_loss: number;
  unsold: Unsold[];
  win_share: number | null;
}

export interface Strategy {
  id: string;
  run_id: string;
  farm_id: string;
  types: StrategyType[];
  decisions: Decision[];
  summary_ru: string;
  summary_en: string;
  metrics: StrategyMetrics;
  flags: string[];
  financing?: Financing | null; // ни одна схема не держит резерв — эта лучшая, но с кредитом
  agro_status: "approved" | "experimental";
  completeness: "full" | "partial";
  unknown_inputs: string[];
}

export interface ExcludedStrategy {
  type: StrategyType;
  constraint: string;
  p_gap_limit: number;
  best_p_gap: number;
  financing_needed_som: number;
}

export interface Provenance {
  model_version: string;
  seed: number;
  n_samples: number;
  years: number[];
  inputs_status: Record<string, "service" | "stub">;
  warnings: string[];
}

export interface GenerateResponse {
  generation_id: string;
  farm_id: string;
  farm_name: string;
  scenario: Scenario;
  schemes_checked: number;
  schemes_truncated: boolean;
  peak_decades: number[];
  strategies: Strategy[];
  excluded: ExcludedStrategy[];
  provenance: Provenance;
  result_hash: string;
}

export interface CashflowMonth {
  month: number;
  cash: Percentiles;
  components: Record<string, number>;
}

export interface CashflowResponse {
  run_id: string;
  strategy_id: string;
  opening_cash_som: number;
  reserve_som: number;
  months: CashflowMonth[];
  gap: CashGap;
  receivable_som: number;
  completeness: "full" | "partial";
  unknown_inputs: string[];
  provenance: Provenance;
}

export interface FieldLoss {
  field_id: string;
  field_name: string;
  crop_id: string;
  yield_loss: number;
}

export interface PlanOutcome {
  income_som: Percentiles;
  cash_p10: number[];
  cash_p50: number[];
  cash_gap: CashGap;
  gross_water_m3: number;
  worst_decade: WorstDecade | null;
  field_losses: FieldLoss[];
  feed_purchase_t: number;
  feed_purchase_som: number;
  unsold: Unsold[];
  decisions: Decision[];
}

export interface StressResponse {
  run_id: string;
  scenario: Scenario;
  baseline: PlanOutcome; // A — исходный план, базовые условия
  stressed: PlanOutcome; // B — исходный план, новые условия
  fixed: PlanOutcome | null; // C — исправленный план, новые условия
  fixed_financing?: Financing | null; // смены культур мало: сколько привлечь плану C (или B)
  fix_needed: boolean;
  fix_found: boolean;
  damage_som: number; // A − B
  adaptation_gain_som: number; // C − B
  change_cost_som: number; // Capex_C + ΔVarCost
  answers: {
    water_decade: WorstDecade | null;
    vulnerable_field: FieldLoss | null;
    cash_gap: CashGap;
    feed_extra_purchase_som: number;
    unsold: Unsold[];
    fix_summary_ru: string;
    fix_summary_en: string;
  };
  elapsed_ms: number;
  reserve_som: number;
  provenance: Provenance;
}

export interface Breakpoint {
  factor: string;
  subject: string | null;
  subject_name_ru: string | null;
  subject_name_en: string | null;
  unit: "percent" | "days" | "celsius";
  base_value: number;
  threshold_value: number;
  delta: number;
  violated_constraint: "cash_gap" | "yield_loss";
  month: number | null;
  field_id: string | null;
  field_name: string | null;
  already_broken: boolean;
  historical_frequency: { count: number; of: number } | null;
  safety_margin_sigma: number | null;
}

export interface BreakpointsResponse {
  run_id: string;
  base_violation: {
    violated_constraint: "cash_gap" | "yield_loss";
    month: number | null;
    field_id: string | null;
    field_name: string | null;
  } | null;
  breakpoints: Breakpoint[];
  holds: string[];
  yield_loss_limit: number;
  provenance: Provenance;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    // ошибки API — problem+json (RFC 9457)
    const problem = await res.json().catch(() => null);
    throw new Error(problem?.detail ?? problem?.title ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** Построить варианты будущего. Повторный вызов с теми же входами отдаёт те же id. */
export function generateStrategies(
  farmId: string,
  body: { scenario?: Partial<Scenario>; seed?: number } = {},
  signal?: AbortSignal,
): Promise<GenerateResponse> {
  return request(`/farms/${encodeURIComponent(farmId)}/strategies:generate`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function getStrategy(strategyId: string, signal?: AbortSignal): Promise<Strategy> {
  return request(`/strategies/${encodeURIComponent(strategyId)}`, { signal });
}

export function getCashflow(runId: string, signal?: AbortSignal): Promise<CashflowResponse> {
  return request(`/runs/${encodeURIComponent(runId)}/cashflow`, { signal });
}

export function stressRun(
  runId: string,
  scenario: Partial<Scenario> & { with_fix?: boolean },
  signal?: AbortSignal,
): Promise<StressResponse> {
  return request(`/runs/${encodeURIComponent(runId)}/stress`, {
    method: "POST",
    body: JSON.stringify(scenario),
    signal,
  });
}

export function getBreakpoints(runId: string, signal?: AbortSignal): Promise<BreakpointsResponse> {
  return request(`/runs/${encodeURIComponent(runId)}/breakpoints`, { signal });
}

/** Где главный экран и шапка находят выбранную стратегию (ключи localStorage). */
export const STORAGE_KEYS = {
  runId: "agroshift.runId",
  built: "agroshift.strategies.built",
  lang: "agroshift.lang",
} as const;
