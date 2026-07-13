"use client";

import { useEffect, useRef, useState } from "react";
import type { SensorData } from "@/lib/api";
import type { WsStatus } from "@/hooks/useRealtimeData";

interface ConnectionCardProps {
  data: SensorData | null;
  wsStatus: WsStatus;
  refreshMs: number;
}

function formatElapsedThai(ageMs: number): string {
  const totalSec = Math.max(0, Math.round(ageMs / 1000));
  const days = Math.floor(totalSec / 86400);
  const hours = Math.floor((totalSec % 86400) / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;

  if (totalSec < 60) return `${seconds} วินาที`;
  if (totalSec < 3600) return seconds === 0 ? `${Math.floor(totalSec / 60)} นาที` : `${Math.floor(totalSec / 60)} นาที ${seconds} วินาที`;
  if (totalSec < 86400) return minutes === 0 ? `${Math.floor(totalSec / 3600)} ชั่วโมง` : `${Math.floor(totalSec / 3600)} ชั่วโมง ${minutes} นาที`;
  return hours === 0 ? `${days} วัน` : `${days} วัน ${hours} ชั่วโมง`;
}

export default function ConnectionCard({ data, wsStatus, refreshMs }: ConnectionCardProps) {
  const [, tick] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => tick((n) => n + 1), 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const deviceOfflineThresholdMs = Math.max(30000, refreshMs * 10);
  const now = Date.now();
  const ts = data?.timestamp_ms ? Number(data.timestamp_ms) : null;
  const ageMs = ts ? Math.max(0, now - ts) : null;

  let dot: "online" | "offline" | "checking" = "checking";
  let stateLabel = "Checking...";
  let metaLabel = "รอข้อมูลจากอุปกรณ์";

  if (wsStatus === "offline") {
    dot = "offline";
    stateLabel = "No Network";
    metaLabel = "ไม่มีการเชื่อมต่ออินเทอร์เน็ต";
  } else if (ageMs !== null) {
    const elapsed = formatElapsedThai(ageMs);
    if (ageMs <= deviceOfflineThresholdMs) {
      dot = "online";
      stateLabel = "Online";
      metaLabel = `อัปเดตล่าสุด ${elapsed} ที่แล้ว`;
    } else {
      dot = "offline";
      stateLabel = "Offline";
      metaLabel = `ขาดข้อมูลมาแล้ว ${elapsed}`;
    }
  }

  return (
    <div className="panel">
      <div className="panel-title">
        <span className="panel-title-icon">📡</span> Device Connection
      </div>
      <div className="connection-card">
        <span className={`connection-dot ${dot}`} />
        <div className="connection-info">
          <p className="connection-state">{stateLabel}</p>
          <p className="connection-meta">{metaLabel}</p>
        </div>
      </div>
    </div>
  );
}
