"use client";

import type { SensorData } from "@/lib/api";
import { fmt } from "@/lib/api";

interface StatusCardsProps {
  data: SensorData | null;
}

function StatusCard({
  id,
  title,
  icon,
  status,
  message,
  action,
}: {
  id: string;
  title: string;
  icon: string;
  status?: string;
  message?: string;
  action?: string;
}) {
  const cls = status ? `status-card status-${status}` : "status-card";
  return (
    <article className={cls} id={id}>
      <h3>
        <span>{icon}</span> {title}
      </h3>
      <p className="level">{status || "-"}</p>
      <p className="message">{message || "-"}</p>
      <p className="action">{action || "-"}</p>
    </article>
  );
}

interface KpiCardProps {
  label: string;
  icon: string;
  value: string;
  unit: string;
}

function KpiCard({ label, icon, value, unit }: KpiCardProps) {
  return (
    <article className="kpi-card">
      <span className="kpi-label">
        <span>{icon}</span> {label}
      </span>
      <span className="kpi-value">{value}</span>
      <span className="kpi-unit">{unit}</span>
    </article>
  );
}

export default function SensorCards({ data }: StatusCardsProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Status Cards */}
      <div className="panel">
        <div className="panel-title">
          <span className="panel-title-icon">⚠️</span> สถานะความเสี่ยง
        </div>
        <div className="status-grid">
          <StatusCard
            id="vpdCard"
            title="VPD Status"
            icon="💗"
            status={data?.vpd_status}
            message={data?.vpd_message}
            action={data?.vpd_action}
          />
          <StatusCard
            id="phCard"
            title="pH Status"
            icon="🧪"
            status={data?.ph_status}
            message={data?.ph_message}
            action={data?.ph_action}
          />
        </div>
      </div>

      {/* Air Environment */}
      <div className="panel">
        <div className="panel-title">
          <span className="panel-title-icon">🌤️</span> สภาพแวดล้อมอากาศ
        </div>
        <div className="kpi-grid">
          <KpiCard label="Air Temp" icon="🌡️" value={fmt(data?.air_temp, 1)} unit="°C" />
          <KpiCard label="Air Humidity" icon="💧" value={fmt(data?.air_humi, 1)} unit="%RH" />
          <KpiCard label="VPD" icon="📊" value={fmt(data?.vpd_kpa, 2)} unit="kPa" />
          <KpiCard label="Wind Speed" icon="🌬️" value={fmt(data?.wind_speed_avg5m, 2)} unit="m/s" />
          <KpiCard label="Solar" icon="☀️" value={fmt(data?.solar_wm2_est, 1)} unit="W/m²" />
          <KpiCard label="Light" icon="💡" value={fmt(data?.lux, 0)} unit="lux" />
        </div>
      </div>

      {/* Soil Environment */}
      <div className="panel">
        <div className="panel-title">
          <span className="panel-title-icon">🌱</span> สภาพแวดล้อมดิน
        </div>
        <div className="kpi-grid">
          <KpiCard label="Soil Temp" icon="🌡️" value={fmt(data?.soil_temp, 1)} unit="°C" />
          <KpiCard label="Soil Moisture" icon="💦" value={fmt(data?.soil_humi, 1)} unit="%" />
          <KpiCard label="Soil pH" icon="⚗️" value={fmt(data?.ph, 2)} unit="pH" />
          <KpiCard label="EC" icon="⚡" value={fmt(data?.ec, 2)} unit="mS/cm" />
        </div>
      </div>
    </div>
  );
}
