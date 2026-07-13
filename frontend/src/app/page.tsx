"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import TopBar from "@/components/TopBar";
import ConnectionCard from "@/components/ConnectionCard";
import SensorCards from "@/components/SensorCards";
import { useRealtimeData } from "@/hooks/useRealtimeData";

// Lazy-load heavy components to reduce initial bundle
const WeatherPanel = dynamic(() => import("@/components/WeatherPanel"), { ssr: false });
const ChartSection = dynamic(() => import("@/components/ChartSection"), { ssr: false });

type View = "live" | "weather" | "charts";

const REFRESH_MS = Number(process.env.NEXT_PUBLIC_REFRESH_MS ?? 3000);
const DEFAULT_PROVINCE = process.env.NEXT_PUBLIC_TMD_PROVINCE ?? "จันทบุรี";
const DEFAULT_AMPHOE = process.env.NEXT_PUBLIC_TMD_AMPHOE ?? "นายายอาม";
const DEFAULT_TAMBON = process.env.NEXT_PUBLIC_TMD_TAMBON ?? "วังโตนด";
const DEFAULT_FORECAST_DAYS = Number(process.env.NEXT_PUBLIC_TMD_FORECAST_DAYS ?? 7);
const MQTT_TOPIC = process.env.NEXT_PUBLIC_MQTT_TOPIC ?? "durian_farm1/node_sensor";

export default function DashboardPage() {
  const [currentView, setCurrentView] = useState<View>("live");
  const [isKiosk, setIsKiosk] = useState(false);

  const { data, wsStatus, lastUpdatedAt } = useRealtimeData({ refreshMs: REFRESH_MS });

  // Kiosk detection (mobile / small screen → show view switch)
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px), (max-height: 560px)");
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsKiosk(e.matches);
    handler(mq);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const isVisible = (view: View) => !isKiosk || currentView === view;

  return (
    <div className="app-shell">
      <TopBar
        wsStatus={wsStatus}
        lastUpdatedAt={lastUpdatedAt}
        topic={MQTT_TOPIC}
      />

      <main className="main-content">
        {/* View Switch (visible only on mobile/kiosk) */}
        {isKiosk && (
          <nav
            className="view-switch"
            aria-label="Dashboard views"
            style={{ marginBottom: "1rem", display: "flex" }}
          >
            {(["live", "weather", "charts"] as View[]).map((v) => {
              const labels: Record<View, string> = {
                live: "🔴 สถานะสด",
                weather: "⛅ พยากรณ์",
                charts: "📈 กราฟ",
              };
              return (
                <button
                  key={v}
                  type="button"
                  className={`view-switch-btn ${currentView === v ? "active" : ""}`}
                  onClick={() => setCurrentView(v)}
                  aria-pressed={currentView === v}
                >
                  {labels[v]}
                </button>
              );
            })}
          </nav>
        )}

        <div className="dashboard-sections">
          {/* Live View */}
          {isVisible("live") && (
            <section className="live-grid" data-view="live">
              <div className="live-left">
                <ConnectionCard
                  data={data}
                  wsStatus={wsStatus}
                  refreshMs={REFRESH_MS}
                />
              </div>
              <SensorCards data={data} />
            </section>
          )}

          {/* Weather View */}
          {isVisible("weather") && (
            <section data-view="weather">
              <WeatherPanel
                defaultProvince={DEFAULT_PROVINCE}
                defaultAmphoe={DEFAULT_AMPHOE}
                defaultTambon={DEFAULT_TAMBON}
                defaultDurationDays={DEFAULT_FORECAST_DAYS}
              />
            </section>
          )}

          {/* Charts View */}
          {isVisible("charts") && (
            <section data-view="charts">
              <ChartSection />
            </section>
          )}
        </div>
      </main>

      <footer className="footer">
        <p>คณะวิทยาศาสตร์และเทคโนโลยี มหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี</p>
        <p>สาขาวิชาการวิเคราะห์และจัดการข้อมูลขนาดใหญ่</p>
      </footer>
    </div>
  );
}
