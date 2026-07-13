// ── API Types ──────────────────────────────────────────────────────────────

export interface SensorData {
  timestamp_ms?: number;
  air_temp?: number;
  air_humi?: number;
  vpd_kpa?: number;
  wind_speed_avg5m?: number;
  solar_wm2_est?: number;
  lux?: number;
  soil_temp?: number;
  soil_humi?: number;
  ph?: number;
  ec?: number;
  vpd_status?: string;
  vpd_message?: string;
  vpd_action?: string;
  ph_status?: string;
  ph_message?: string;
  ph_action?: string;
}

export interface HistoryPoint {
  timestamp_ms: number;
  value: number;
}

export interface WeatherDay {
  time: string;
  tc_min?: number;
  tc_max?: number;
  rh?: number;
  rain?: number;
  rain_mm?: number;
  rain_pct?: number;
  ws10m?: number;
  cond?: number;
}

export interface WeatherData {
  days?: WeatherDay[];
  location?: {
    province?: string;
    amphoe?: string;
    tambon?: string;
  };
  query_meta?: {
    fallback_used?: boolean;
    used?: {
      scope?: string;
      provider?: string;
    };
  };
}

export interface FarmSummary {
  risk_level?: "normal" | "warning" | "danger";
  headline?: string;
  risk_score?: number;
  reasons?: string[];
  actions?: string[];
}

export interface FarmSummaryResponse {
  place?: { province?: string; amphoe?: string; tambon?: string };
  weather?: WeatherData;
  sensor_latest?: SensorData;
  summary?: FarmSummary;
}

export interface LineAlertStatus {
  enabled: boolean;
  effective_enabled: boolean;
  configured_in_env: boolean;
  persisted?: string;
  notifier_configured: boolean;
  has_default_place: boolean;
  daily_limit: number;
  daily_sent: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...options });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const payload = await res.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ── API Functions ──────────────────────────────────────────────────────────

export const api = {
  latest: () => apiFetch<{ data: SensorData }>("/api/latest"),

  history: (field: string, hours: number) =>
    apiFetch<{ field: string; hours: number; points: HistoryPoint[] }>(
      `/api/history?field=${field}&hours=${hours}`
    ),

  provinces: () => apiFetch<{ items: string[] }>("/api/locations/provinces"),
  amphoes: (province: string) =>
    apiFetch<{ items: string[] }>(`/api/locations/amphoes?province=${encodeURIComponent(province)}`),
  tambons: (province: string, amphoe: string) =>
    apiFetch<{ items: string[] }>(
      `/api/locations/tambons?province=${encodeURIComponent(province)}&amphoe=${encodeURIComponent(amphoe)}`
    ),

  weather: (province: string, amphoe: string, tambon: string, durationDays = 7) =>
    apiFetch<WeatherData>(
      `/api/weather?province=${encodeURIComponent(province)}&amphoe=${encodeURIComponent(amphoe)}&tambon=${encodeURIComponent(tambon)}&duration_days=${durationDays}`
    ),

  weatherRaw: (province: string, amphoe: string, tambon: string, durationDays = 7) =>
    apiFetch<unknown>(
      `/api/weather/raw?province=${encodeURIComponent(province)}&amphoe=${encodeURIComponent(amphoe)}&tambon=${encodeURIComponent(tambon)}&duration_days=${durationDays}`
    ),

  farmSummary: (province: string, amphoe: string, tambon: string, durationDays = 7) =>
    apiFetch<FarmSummaryResponse>(
      `/api/farm-summary?province=${encodeURIComponent(province)}&amphoe=${encodeURIComponent(amphoe)}&tambon=${encodeURIComponent(tambon)}&duration_days=${durationDays}`
    ),

  lineAlertStatus: () => apiFetch<LineAlertStatus>("/api/line/alert-status"),
  lineAlertToggle: (enabled?: boolean) =>
    apiFetch<LineAlertStatus>(
      `/api/line/alert-toggle${enabled !== undefined ? `?enabled=${enabled}` : ""}`,
      { method: "POST" }
    ),
};

// ── Number formatting ──────────────────────────────────────────────────────

export function fmt(v: number | undefined | null, decimals = 2): string {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "-";
  return Number(v).toFixed(decimals);
}
