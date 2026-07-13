"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { api, type WeatherData, type FarmSummary } from "@/lib/api";

// ── Constants ──────────────────────────────────────────────────────────────
const TMD_COND_ICONS: Record<number, string> = {
  1: "☀️", 2: "⛅", 3: "☁️", 4: "🌥️",
  5: "🌦️", 6: "🌧️", 7: "⛈️", 8: "🌩️", 9: "❄️",
};
const TMD_COND_DESC: Record<number, string> = {
  1: "ท้องฟ้าแจ่มใส", 2: "มีเมฆบางส่วน", 3: "เมฆมาก", 4: "เมฆครึ้ม",
  5: "ฝนเล็กน้อย", 6: "ฝนปานกลาง", 7: "ฝนหนัก", 8: "ฝนฟ้าคะนอง", 9: "อากาศหนาวจัด",
};
const DAYS_TH = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์"];
const WEATHER_LOC_KEY = "weather_location_tmd_place";
const WEATHER_AUTO_REFRESH_MS = 15 * 60 * 1000;
const COMPARE_FIELDS = ["tc_min", "tc_max", "rh", "rain", "ws10m", "cond"] as const;

function isSameLocalDate(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function msUntilNextMidnight() {
  const now = new Date();
  const next = new Date(now);
  next.setHours(24, 0, 2, 0);
  return Math.max(1000, next.getTime() - now.getTime());
}
function toNum(v: unknown): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
function closeNums(a: unknown, b: unknown, tol = 0.01): boolean {
  if (a == null && b == null) return true;
  if (a == null || b == null) return false;
  const av = Number(a), bv = Number(b);
  if (!Number.isFinite(av) || !Number.isFinite(bv)) return String(a) === String(b);
  return Math.abs(av - bv) <= tol;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function WeatherDayCard({ day }: { day: WeatherData["days"] extends (infer D)[] | undefined ? D : never }) {
  if (!day || typeof day !== "object") return null;
  const d = new Date((day as { time: string }).time);
  const dayObj = day as {
    time: string; tc_min?: number; tc_max?: number;
    rh?: number; rain?: number; rain_mm?: number; rain_pct?: number;
    ws10m?: number; cond?: number;
  };
  const isToday = isSameLocalDate(d, new Date());
  const dayLabel = isToday ? "วันนี้" : DAYS_TH[d.getDay()];
  const cond = dayObj.cond ?? 0;
  const icon = TMD_COND_ICONS[cond] ?? "☁️";
  const desc = TMD_COND_DESC[cond] ?? "ไม่ระบุ";
  const cardCls = [1, 2].includes(cond) ? "sun" : [5, 8, 9].includes(cond) ? "rain" : cond === 7 ? "storm" : "cloud";
  const tmax = dayObj.tc_max != null ? Number(dayObj.tc_max).toFixed(1) : "-";
  const tmin = dayObj.tc_min != null ? Number(dayObj.tc_min).toFixed(1) : "-";
  const rainMmRaw = toNum(dayObj.rain_mm) ?? toNum(dayObj.rain);
  const rainPctRaw = toNum(dayObj.rain_pct) ?? (rainMmRaw != null && rainMmRaw >= 0 && rainMmRaw <= 100 ? rainMmRaw : null);
  const rainMmText = rainMmRaw != null ? `${rainMmRaw.toFixed(1)} มม.` : "- มม.";
  const rainPctText = rainPctRaw != null ? `${rainPctRaw.toFixed(0)}%` : "-%";
  const rh = dayObj.rh != null ? Number(dayObj.rh).toFixed(0) : "-";
  const wind = dayObj.ws10m != null ? Number(dayObj.ws10m).toFixed(1) : "-";

  return (
    <div className={`weather-day-card ${cardCls}`}>
      <div className="weather-day-label">{dayLabel}</div>
      <div className="weather-day-date">{d.toLocaleDateString("th-TH", { day: "numeric", month: "short" })}</div>
      <div className="weather-day-icon">{icon}</div>
      <div className="weather-day-desc">{desc}</div>
      <div className="weather-day-temp">
        <span className="temp-max">{tmax}°</span>
        <span className="temp-sep">/</span>
        <span className="temp-min">{tmin}°</span>
      </div>
      <div className="weather-day-rain">💧 RH {rh}% · ฝน {rainMmText} · โอกาสฝน {rainPctText}</div>
      <div className="weather-day-wind">🌬️ {wind} m/s</div>
    </div>
  );
}

function FarmSummaryCard({ summary }: { summary: FarmSummary | undefined }) {
  if (!summary) return null;
  const cls = summary.risk_level === "danger" ? "danger" : summary.risk_level === "warning" ? "warning" : "normal";
  return (
    <div className={`farm-summary-card ${cls}`}>
      <h3>📋 สรุปข้อมูลสวน + พยากรณ์</h3>
      <p className="farm-summary-headline">{summary.headline || "-"}</p>
      <p className="farm-summary-list">
        {(summary.reasons || []).map((r) => `- ${r}`).join("\n") || "-"}
      </p>
      <p className="farm-summary-list" style={{ marginTop: "0.5rem" }}>
        {(summary.actions || []).map((a) => `▶ ${a}`).join("\n") || "-"}
      </p>
    </div>
  );
}

// ── Main WeatherPanel ──────────────────────────────────────────────────────

interface WeatherPanelProps {
  defaultProvince?: string;
  defaultAmphoe?: string;
  defaultTambon?: string;
  defaultDurationDays?: number;
}

export default function WeatherPanel({
  defaultProvince = "",
  defaultAmphoe = "",
  defaultTambon = "",
  defaultDurationDays = 7,
}: WeatherPanelProps) {
  const [provinces, setProvinces] = useState<string[]>([]);
  const [amphoes, setAmphoes] = useState<string[]>([]);
  const [tambons, setTambons] = useState<string[]>([]);
  const [selProvince, setSelProvince] = useState("");
  const [selAmphoe, setSelAmphoe] = useState("");
  const [selTambon, setSelTambon] = useState("");
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null);
  const [farmSummary, setFarmSummary] = useState<FarmSummary | undefined>();
  const [locationBadge, setLocationBadge] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [compareData, setCompareData] = useState<{ system: unknown; raw: unknown; rows: React.ReactNode } | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareUpdated, setCompareUpdated] = useState("ยังไม่เริ่มเทียบ");
  const [compareSummary, setCompareSummary] = useState("กดปุ่ม \"เทียบข้อมูล\" เพื่อดึงข้อมูลล่าสุดทั้งสองฝั่ง");
  const activePlace = useRef({ province: "", amphoe: "", tambon: "" });
  const autoRefreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const midnightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load provinces on mount
  useEffect(() => {
    api.provinces().then((r) => setProvinces(r.items)).catch(() => {});
  }, []);

  // Load amphoes when province changes
  useEffect(() => {
    if (!selProvince) { setAmphoes([]); setTambons([]); return; }
    api.amphoes(selProvince).then((r) => setAmphoes(r.items)).catch(() => setAmphoes([]));
  }, [selProvince]);

  // Load tambons when amphoe changes
  useEffect(() => {
    if (!selProvince || !selAmphoe) { setTambons([]); return; }
    api.tambons(selProvince, selAmphoe).then((r) => setTambons(r.items)).catch(() => setTambons([]));
  }, [selProvince, selAmphoe]);

  const loadWeather = useCallback(async (place: { province: string; amphoe: string; tambon: string }, persist = true) => {
    if (!place.province) return;
    setLoading(true);
    setError(null);
    activePlace.current = place;
    try {
      const [wd, fs] = await Promise.all([
        api.weather(place.province, place.amphoe, place.tambon, defaultDurationDays),
        api.farmSummary(place.province, place.amphoe, place.tambon, defaultDurationDays),
      ]);
      setWeatherData(wd);
      setFarmSummary(fs.summary);
      const loc = wd.location || {};
      const parts = [loc.tambon || place.tambon, loc.amphoe || place.amphoe, loc.province || place.province].filter(Boolean);
      const fallback = wd.query_meta?.fallback_used;
      const provider = wd.query_meta?.used?.provider;
      const scope = wd.query_meta?.used?.scope;
      const suffix = provider === "openweather" ? " (สำรอง: OpenWeather)" : fallback && scope ? ` (fallback: ระดับ ${scope})` : "";
      setLocationBadge(parts.join(" ") + suffix);
      if (persist) {
        try { localStorage.setItem(WEATHER_LOC_KEY, JSON.stringify(place)); } catch {}
      }
    } catch (e) {
      setError((e as Error).message || "โหลดพยากรณ์ไม่สำเร็จ");
    } finally {
      setLoading(false);
    }
  }, [defaultDurationDays]);

  const setupAutoRefresh = useCallback(() => {
    if (autoRefreshTimer.current) clearInterval(autoRefreshTimer.current);
    autoRefreshTimer.current = setInterval(() => {
      if (activePlace.current.province) loadWeather(activePlace.current, false);
    }, WEATHER_AUTO_REFRESH_MS);
  }, [loadWeather]);

  const setupMidnightRefresh = useCallback(() => {
    if (midnightTimer.current) clearTimeout(midnightTimer.current);
    midnightTimer.current = setTimeout(async () => {
      if (activePlace.current.province) await loadWeather(activePlace.current, false);
      setupMidnightRefresh();
    }, msUntilNextMidnight());
  }, [loadWeather]);

  // Init: restore saved location or use default
  useEffect(() => {
    let saved: { province?: string; amphoe?: string; tambon?: string } | null = null;
    try {
      const raw = localStorage.getItem(WEATHER_LOC_KEY);
      if (raw) saved = JSON.parse(raw);
    } catch {}
    const initProvince = saved?.province?.trim() || defaultProvince;
    const initAmphoe = saved?.amphoe?.trim() || defaultAmphoe;
    const initTambon = saved?.tambon?.trim() || defaultTambon;
    setSelProvince(initProvince);
    setSelAmphoe(initAmphoe);
    setSelTambon(initTambon);
    if (initProvince) {
      loadWeather({ province: initProvince, amphoe: initAmphoe, tambon: initTambon });
    }
    setupAutoRefresh();
    setupMidnightRefresh();
    return () => {
      if (autoRefreshTimer.current) clearInterval(autoRefreshTimer.current);
      if (midnightTimer.current) clearTimeout(midnightTimer.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && activePlace.current.province) {
        loadWeather(activePlace.current, false);
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [loadWeather]);

  const handleLoad = () => {
    if (!selProvince) { setError("กรุณาระบุจังหวัด"); return; }
    loadWeather({ province: selProvince, amphoe: selAmphoe, tambon: selTambon });
  };

  // Compare panel
  const handleCompare = async () => {
    if (showCompare) { setShowCompare(false); return; }
    const place = { province: selProvince, amphoe: selAmphoe, tambon: selTambon };
    if (!place.province) { setError("กรุณาระบุจังหวัด"); return; }
    setCompareLoading(true);
    setShowCompare(true);
    try {
      const [systemData, rawData] = await Promise.all([
        api.weather(place.province, place.amphoe, place.tambon, defaultDurationDays),
        api.weatherRaw(place.province, place.amphoe, place.tambon, defaultDurationDays),
      ]);

      const rawPayload = (rawData as { raw_payload?: { WeatherForecasts?: { forecasts?: unknown[] }[] } }).raw_payload;
      const rawDays = (rawPayload?.WeatherForecasts?.[0]?.forecasts ?? [])
        .filter(Boolean)
        .map((x: unknown) => {
          const f = x as { time?: string; data?: Record<string, unknown> };
          return { time: f.time, ...(f.data || {}) };
        });

      const systemDays = Array.isArray((systemData as { days?: unknown[] }).days)
        ? ((systemData as unknown) as { days: Record<string, unknown>[] }).days
        : [];
      const rawMap = new Map(rawDays.map((r: Record<string, unknown>) => [String(r.time ?? ""), r]));

      let total = 0, matched = 0;
      const rows: React.ReactNode[] = [];
      systemDays.forEach((sDay: Record<string, unknown>, idx: number) => {
        const key = String(sDay.time ?? "");
        const rDay: Record<string, unknown> = (rawMap.get(key) as Record<string, unknown>) || rawDays[idx] || {};
        const dayLabel = sDay.time ? new Date(sDay.time as string).toLocaleDateString("th-TH", { day: "2-digit", month: "short" }) : `#${idx + 1}`;
        COMPARE_FIELDS.forEach((field) => {
          const sv = sDay[field] ?? null;
          const rv = rDay[field] ?? null;
          const ok = closeNums(sv, rv);
          total++; if (ok) matched++;
          rows.push(
            <tr key={`${idx}-${field}`}>
              <td>{dayLabel}</td>
              <td>{field}</td>
              <td>{sv != null ? String(sv) : "-"}</td>
              <td>{rv != null ? String(rv) : "-"}</td>
              <td className={ok ? "cmp-ok" : "cmp-miss"}>{ok ? "ตรง" : "ต่าง"}</td>
            </tr>
          );
        });
      });

      const pct = total > 0 ? ((matched / total) * 100).toFixed(1) : "0.0";
      const meta = (systemData as { query_meta?: { fallback_used?: boolean; used?: { scope?: string } } }).query_meta;
      const fallbackText = meta?.fallback_used ? `มี fallback ระดับ ${meta.used?.scope ?? "-"}` : "ไม่ใช้ fallback";
      setCompareSummary(`ผลเทียบ: ตรง ${matched}/${total} ฟิลด์ (${pct}%) · ${fallbackText}`);
      setCompareUpdated(`อัปเดตล่าสุด ${new Date().toLocaleString("th-TH")}`);
      setCompareData({ system: systemData, raw: rawData, rows });
    } catch (e) {
      setCompareSummary(`เกิดข้อผิดพลาด: ${(e as Error).message}`);
      setCompareData(null);
    } finally {
      setCompareLoading(false);
    }
  };

  const days = weatherData?.days ?? [];

  return (
    <div className="panel">
      {/* Header */}
      <div className="weather-header">
        <div>
          <div className="panel-title">
            <span className="panel-title-icon">⛅</span> พยากรณ์อากาศ 7 วัน
          </div>
          {locationBadge && (
            <span className="weather-location-badge">📍 {locationBadge}</span>
          )}
        </div>
        <div className="weather-location-form">
          <select
            className="weather-select"
            id="weatherProvinceInput"
            value={selProvince}
            onChange={(e) => { setSelProvince(e.target.value); setSelAmphoe(""); setSelTambon(""); }}
          >
            <option value="">เลือกจังหวัด</option>
            {provinces.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>

          <select
            className="weather-select"
            id="weatherAmphoeInput"
            value={selAmphoe}
            onChange={(e) => { setSelAmphoe(e.target.value); setSelTambon(""); }}
            disabled={!selProvince}
          >
            <option value="">อำเภอ (ไม่บังคับ)</option>
            {amphoes.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>

          <select
            className="weather-select"
            id="weatherTambonInput"
            value={selTambon}
            onChange={(e) => setSelTambon(e.target.value)}
            disabled={!selAmphoe}
          >
            <option value="">ตำบล (ไม่บังคับ)</option>
            {tambons.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          <button className="weather-btn" id="weatherLoadBtn" onClick={handleLoad} disabled={loading}>
            {loading ? "⏳" : "☁️"} {loading ? "โหลด..." : "โหลด"}
          </button>
          <button
            className="weather-btn weather-btn-compare"
            id="weatherCompareBtn"
            onClick={handleCompare}
            disabled={compareLoading}
          >
            {showCompare ? "🙈 ซ่อนการเทียบ" : "🔀 เทียบข้อมูล"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && <p className="weather-empty weather-error">⚠️ {error}</p>}

      {/* Forecast Cards */}
      <div className="weather-forecast-grid">
        {days.length === 0 && !loading && !error && (
          <p className="weather-empty">กรุณาระบุจังหวัด/อำเภอ/ตำบล เพื่อดูพยากรณ์อากาศจาก TMD</p>
        )}
        {loading && <p className="weather-empty">⏳ กำลังโหลดพยากรณ์อากาศ<span className="loading-dots" /></p>}
        {!loading && days.map((day) => (
          <WeatherDayCard key={(day as { time: string }).time} day={day} />
        ))}
      </div>

      {/* Farm Summary */}
      <FarmSummaryCard summary={farmSummary} />

      {/* Compare Panel */}
      {showCompare && (
        <div className="weather-compare-panel">
          <div className="weather-compare-head">
            <span className="weather-compare-title">🔀 ตรวจความตรงแบบเรียลไทม์: ระบบ vs ข้อมูลดิบ TMD</span>
            <span className="weather-compare-updated">{compareUpdated}</span>
          </div>
          <p className="weather-compare-summary">{compareSummary}</p>
          {compareData && (
            <>
              <div className="weather-compare-grid">
                <div className="weather-compare-json-card">
                  <h4>🔧 ข้อมูลที่ระบบใช้งานจริง (/api/weather)</h4>
                  <pre>{JSON.stringify(compareData.system, null, 2)}</pre>
                </div>
                <div className="weather-compare-json-card">
                  <h4>🗄️ ข้อมูลดิบจาก TMD (/api/weather/raw)</h4>
                  <pre>{JSON.stringify(compareData.raw, null, 2)}</pre>
                </div>
              </div>
              <div className="weather-compare-table-wrap">
                <table className="weather-compare-table">
                  <thead>
                    <tr>
                      <th>วัน</th><th>ฟิลด์</th><th>ระบบ</th><th>TMD ดิบ</th><th>ผลเทียบ</th>
                    </tr>
                  </thead>
                  <tbody>{compareData.rows}</tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
