"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type LineAlertStatus } from "@/lib/api";
import type { WsStatus } from "@/hooks/useRealtimeData";

interface TopBarProps {
  wsStatus: WsStatus;
  lastUpdatedAt: number | null;
  topic?: string;
}

function formatUpdated(ms: number | null): string {
  if (!ms) return "รอข้อมูล...";
  return `อัปเดต: ${new Date(ms).toLocaleString("th-TH")}`;
}

function WsStatusBadge({ status }: { status: WsStatus }) {
  const map = {
    connected: { dot: "online", label: "Connected" },
    connecting: { dot: "checking", label: "Connecting..." },
    disconnected: { dot: "offline", label: "Disconnected" },
    offline: { dot: "offline", label: "Offline" },
  };
  const { dot, label } = map[status];
  return (
    <span className="badge">
      <span className={`connection-dot ${dot}`} style={{ display: "inline-block" }} />
      {label}
    </span>
  );
}

export default function TopBar({ wsStatus, lastUpdatedAt, topic }: TopBarProps) {
  const [lineStatus, setLineStatus] = useState<LineAlertStatus | null>(null);
  const [toggling, setToggling] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.lineAlertStatus();
      setLineStatus(s);
    } catch {}
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === "visible") fetchStatus(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [fetchStatus]);

  const handleToggle = async () => {
    if (toggling) return;
    setToggling(true);
    try {
      const s = await api.lineAlertToggle();
      setLineStatus(s);
    } catch {}
    setToggling(false);
  };

  const isOn = lineStatus?.enabled ?? false;
  const isBlocked = lineStatus
    ? !lineStatus.notifier_configured || !lineStatus.has_default_place
    : false;

  const lineTitle = isBlocked
    ? "ยังไม่พร้อมใช้งาน: กรุณาตั้งค่า LINE token/user และ TMD_PROVINCE"
    : "กดเพื่อสลับเปิด/ปิดการแจ้งเตือน LINE อัตโนมัติ";

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="topbar-eyebrow">Durian IoT Operations</span>
        <h1 className="topbar-title">
          <span className="topbar-title-icon">🌳</span> สวนพรรณมณี
        </h1>
        {topic && <p className="topbar-subtitle">MQTT: {topic}</p>}
      </div>

      <div className="topbar-actions">
        <button
          id="lineAlertToggleBtn"
          className={`line-alert-btn ${isOn ? "on" : "off"} ${isBlocked ? "blocked" : ""}`}
          type="button"
          aria-pressed={isOn}
          onClick={handleToggle}
          disabled={toggling || isBlocked}
          title={lineTitle}
        >
          {isOn ? "🔔" : "🔕"} LINE Auto Alert: {isOn ? "ON" : "OFF"}
        </button>

        <WsStatusBadge status={wsStatus} />

        <span className="badge">
          {formatUpdated(lastUpdatedAt)}
        </span>
      </div>
    </header>
  );
}
