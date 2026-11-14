import type { Point, Polygon } from "geojson";

export type Language = "ru" | "ky" | "en";
export interface Source {
  source_type: string;
  confidence: number;
  note: string;
  citation?: string;
}
export interface Season {
  id: string;
  crop_id: string;
  crop_variant_id: string;
  year: number;
  is_main: boolean;
  sowing_date: string | null;
  harvest_date: string | null;
  planned_yield_t_ha: number | null;
}
export interface Field {
  id: string;
  farm_id: string;
  name: string;
  area_ha: number;
  geometry: Polygon | null;
  location: Point | null;
  irrigation_method: string;
  soil_type: string | null;
  elevation_m: number | null;
  taw_mm_per_m: number | null;
  seasons: Season[];
  provenance: Record<string, Source>;
}
export interface Farm {
  id: string;
  name: string;
  district: string | null;
  village: string | null;
  language: Language;
  area_ha: number;
  cash_som: number | null;
  family_reserve_som: number | null;
  fields: Field[];
  herds: { id: string; species: string; purpose: string; head_count: number }[];
  cash_accounts: { id: string; balance_som: number }[];
  water_rights: {
    turn_interval_days: number | null;
    turn_hours: number | null;
    flow_l_s: number | null;
  }[];
  orchards: { field_id: string }[];
  completeness: string;
  unknown_inputs: string[];
  consent_agronomist: boolean;
  consent_canal_plan: boolean;
  consent_analytics: boolean;
}
export interface Crop {
  id: string;
  code: string;
  name_ru: string;
  name_ky: string;
  name_en: string;
  kc_ini: number;
  kc_mid: number;
  kc_end: number;
  root_depth_m: number;
  p_depletion: number;
  ky: number;
  stage_days: number[];
  provenance: Record<string, Source>;
  variants: { id: string; code: string; product: string; yield_potential_t_ha: number }[];
  price: { price_som: number; unit: string; source_note: string } | null;
}
export interface Scenario {
  id: string;
  preset_code: string;
  name: string;
  water_supply_factor: number;
  water_supply_months: number[] | null;
  supply_shift_days: number;
  price_factors: Record<string, number>;
  payment_delay_days: number;
  climate_params: { year: number | null; percentile: number | null };
  temp_delta_c: number;
  precip_factor: number;
  yield_factor: number;
}
export interface Rotation {
  id: string;
  name: string;
  sequence: string[];
  status: string;
}
export interface FarmWrite {
  name?: string;
  district?: string | null;
  village?: string | null;
  language?: Language;
  cash_som?: number | null;
  family_reserve_som?: number | null;
  cow_count?: number | null;
  consent_agronomist?: boolean;
  consent_canal_plan?: boolean;
  consent_analytics?: boolean;
}
export interface FieldWrite {
  name?: string;
  area_ha?: number;
  location?: Point;
  irrigation_method?: string;
  season?: {
    crop_variant_id: string;
    year: number;
    sowing_date: string | null;
    harvest_date: string | null;
  };
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Demo-Role": "farmer",
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const errors = body.errors
      ?.map((e: { msg: string }) => e.msg.replace(/^Value error, /, ""))
      .join(". ");
    throw new ApiError(errors || body.detail || `HTTP ${response.status}`, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const api = {
  farms: async () => {
    const items: Farm[] = [];
    let cursor: string | null = null;
    do {
      const page: { items: Farm[]; next_cursor: string | null } = await request(
        `/farms?limit=100${cursor ? `&cursor=${cursor}` : ""}`,
      );
      items.push(...page.items);
      cursor = page.next_cursor;
    } while (cursor);
    return items;
  },
  farm: (id: string) => request<Farm>(`/farms/${id}`),
  crops: () => request<Crop[]>("/catalog/crops"),
  scenarios: () => request<Scenario[]>("/scenarios/presets"),
  rotations: () => request<Rotation[]>("/catalog/rotations?zone=chuy"),
  createFarm: (body: FarmWrite, key: string) =>
    request<Farm>("/farms", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Idempotency-Key": key },
    }),
  updateFarm: (id: string, body: FarmWrite) =>
    request<Farm>(`/farms/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteFarm: (id: string) => request<void>(`/farms/${id}`, { method: "DELETE" }),
  createField: (farmId: string, body: FieldWrite, key: string) =>
    request<Field>(`/farms/${farmId}/fields`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Idempotency-Key": key },
    }),
  updateField: (farmId: string, id: string, body: FieldWrite) =>
    request<Field>(`/farms/${farmId}/fields/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteField: (farmId: string, id: string) =>
    request<void>(`/farms/${farmId}/fields/${id}`, { method: "DELETE" }),
};
