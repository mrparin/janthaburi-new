"use client";

import { useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";

// Chart.js types (dynamic import)
declare global {
  interface Window {
    Chart: {
      new (ctx: HTMLCanvasElement, config: unknown): ChartInstance;
      defaults: {
        color: string;
        borderColor: string;
        interaction: { mode: string; intersect: boolean; axis: string };
        elements: { point: { radius: number; hoverRadius: number; hitRadius: number } };
      };
    };
  }
}

interface ChartInstance {
  data: { labels: string[]; datasets: { data: (number | null)[] }[] };
  update(): void;
  destroy(): void;
}

const AXIS_COLOR = "#6aae76";
const GRID_COLOR = "rgba(106, 174, 118, 0.18)";

function buildLineConfig(
  label: string,
  color: string,
  yAxisID?: string
): Record<string, unknown> {
  return {
    label,
    data: [],
    borderColor: color,
    backgroundColor: color,
    tension: 0.25,
    ...(yAxisID ? { yAxisID } : {}),
  };
}

function scaleOpts(title?: string, position: "left" | "right" = "left") {
  return {
    type: "linear",
    position,
    ...(title ? { title: { display: true, text: title, color: AXIS_COLOR } } : {}),
    ticks: { color: AXIS_COLOR },
    grid: {
      color: GRID_COLOR,
      ...(position === "right" ? { drawOnChartArea: false } : {}),
    },
  };
}

export default function ChartSection() {
  const vpdRef = useRef<HTMLCanvasElement>(null);
  const phRef = useRef<HTMLCanvasElement>(null);
  const airTrendRef = useRef<HTMLCanvasElement>(null);
  const soilTrendRef = useRef<HTMLCanvasElement>(null);
  const chartsRef = useRef<ChartInstance[]>([]);
  const loadedRef = useRef(false);

  const initCharts = useCallback(() => {
    const Chart = window.Chart;
    if (!Chart) return;

    // Set global defaults once
    Chart.defaults.color = AXIS_COLOR;
    Chart.defaults.borderColor = GRID_COLOR;
    Chart.defaults.interaction = { mode: "nearest", intersect: false, axis: "x" };
    Chart.defaults.elements.point.radius = 2;
    Chart.defaults.elements.point.hoverRadius = 6;
    Chart.defaults.elements.point.hitRadius = 12;

    const commonScales = {
      x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
      y: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
    };

    const charts: ChartInstance[] = [];

    if (vpdRef.current && !chartsRef.current[0]) {
      charts.push(new Chart(vpdRef.current, {
        type: "line",
        data: { labels: [], datasets: [buildLineConfig("VPD kPa", "#d9a441")] },
        options: { animation: false, plugins: { legend: { display: false } }, scales: commonScales },
      }));
    }

    if (phRef.current && !chartsRef.current[1]) {
      charts.push(new Chart(phRef.current, {
        type: "line",
        data: { labels: [], datasets: [buildLineConfig("pH", "#b93b32")] },
        options: { animation: false, plugins: { legend: { display: false } }, scales: commonScales },
      }));
    }

    if (airTrendRef.current && !chartsRef.current[2]) {
      charts.push(new Chart(airTrendRef.current, {
        type: "line",
        data: {
          labels: [],
          datasets: [
            buildLineConfig("อุณหภูมิอากาศ (°C)", "#4f7f2d", "yTemp"),
            buildLineConfig("ความชื้นอากาศ (%RH)", "#3e7f7f", "yHumi"),
          ],
        },
        options: {
          animation: false,
          plugins: { legend: { display: true } },
          scales: {
            yTemp: scaleOpts("อุณหภูมิ (°C)", "left"),
            yHumi: scaleOpts("ความชื้น (%RH)", "right"),
            x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
          },
        },
      }));
    }

    if (soilTrendRef.current && !chartsRef.current[3]) {
      charts.push(new Chart(soilTrendRef.current, {
        type: "line",
        data: {
          labels: [],
          datasets: [
            buildLineConfig("อุณหภูมิดิน (°C)", "#8a5a2b", "yTemp"),
            buildLineConfig("ความชื้นดิน (%)", "#4f7f2d", "yHumi"),
          ],
        },
        options: {
          animation: false,
          plugins: { legend: { display: true } },
          scales: {
            yTemp: scaleOpts("อุณหภูมิ (°C)", "left"),
            yHumi: scaleOpts("ความชื้น (%)", "right"),
            x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
          },
        },
      }));
    }

    chartsRef.current = charts;
  }, []);

  const refreshCharts = useCallback(async () => {
    const charts = chartsRef.current;
    if (charts.length < 4) return;

    try {
      const [vpd, ph] = await Promise.all([
        api.history("vpd_kpa", 24),
        api.history("ph", 168),
      ]);
      const vpdChart = charts[0];
      vpdChart.data.labels = vpd.points.map((p) => new Date(p.timestamp_ms).toLocaleTimeString());
      vpdChart.data.datasets[0].data = vpd.points.map((p) => p.value);
      vpdChart.update();

      const phChart = charts[1];
      phChart.data.labels = ph.points.map((p) => new Date(p.timestamp_ms).toLocaleTimeString());
      phChart.data.datasets[0].data = ph.points.map((p) => p.value);
      phChart.update();
    } catch {}

    try {
      const [airTemp, airHumi, soilTemp, soilHumi] = await Promise.all([
        api.history("air_temp", 24),
        api.history("air_humi", 24),
        api.history("soil_temp", 24),
        api.history("soil_humi", 24),
      ]);

      function merge(seriesA: typeof airTemp["points"], seriesB: typeof airTemp["points"]) {
        const mapA = new Map(seriesA.map((p) => [p.timestamp_ms, p.value]));
        const mapB = new Map(seriesB.map((p) => [p.timestamp_ms, p.value]));
        const ts = Array.from(new Set([...mapA.keys(), ...mapB.keys()])).sort((a, b) => a - b);
        return {
          labels: ts.map((t) => new Date(t).toLocaleTimeString()),
          aValues: ts.map((t) => mapA.get(t) ?? null),
          bValues: ts.map((t) => mapB.get(t) ?? null),
        };
      }

      const airMerged = merge(airTemp.points, airHumi.points);
      const airChart = charts[2];
      airChart.data.labels = airMerged.labels;
      airChart.data.datasets[0].data = airMerged.aValues;
      airChart.data.datasets[1].data = airMerged.bValues;
      airChart.update();

      const soilMerged = merge(soilTemp.points, soilHumi.points);
      const soilChart = charts[3];
      soilChart.data.labels = soilMerged.labels;
      soilChart.data.datasets[0].data = soilMerged.aValues;
      soilChart.data.datasets[1].data = soilMerged.bValues;
      soilChart.update();
    } catch {}
  }, []);

  useEffect(() => {
    // Lazy-load Chart.js from CDN if not loaded yet
    if (loadedRef.current) { initCharts(); refreshCharts(); return; }

    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/chart.js";
    script.onload = () => {
      loadedRef.current = true;
      initCharts();
      refreshCharts();
    };
    document.head.appendChild(script);

    const refreshInterval = setInterval(refreshCharts, 30000);
    return () => {
      clearInterval(refreshInterval);
      chartsRef.current.forEach((c) => { try { c.destroy(); } catch {} });
      chartsRef.current = [];
    };
  }, [initCharts, refreshCharts]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="chart-grid">
        <div className="chart-card">
          <h3>📈 VPD Last 24h</h3>
          <div className="chart-canvas-wrap">
            <canvas ref={vpdRef} id="vpdChart" />
          </div>
        </div>
        <div className="chart-card">
          <h3>🧪 pH Last 7d</h3>
          <div className="chart-canvas-wrap">
            <canvas ref={phRef} id="phChart" />
          </div>
        </div>
      </div>
      <div className="chart-grid">
        <div className="chart-card">
          <h3>🌡️ แนวโน้มอุณหภูมิและความชื้นอากาศ (24h)</h3>
          <div className="chart-canvas-wrap">
            <canvas ref={airTrendRef} id="airTrendChart" />
          </div>
        </div>
        <div className="chart-card">
          <h3>🌱 แนวโน้มอุณหภูมิและความชื้นดิน (24h)</h3>
          <div className="chart-canvas-wrap">
            <canvas ref={soilTrendRef} id="soilTrendChart" />
          </div>
        </div>
      </div>
    </div>
  );
}
