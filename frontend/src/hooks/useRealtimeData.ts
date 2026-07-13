"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SensorData } from "@/lib/api";

export type WsStatus = "connecting" | "connected" | "disconnected" | "offline";

interface UseRealtimeDataOptions {
  /** How many ms between server pushes (matches REFRESH_SECONDS). */
  refreshMs?: number;
  /** How long without a message before considered stale (ms). */
  staleThresholdMs?: number;
}

interface UseRealtimeDataReturn {
  data: SensorData | null;
  wsStatus: WsStatus;
  lastUpdatedAt: number | null;
}

const BACKOFF_INITIAL = 1000;
const BACKOFF_MAX = 10000;

export function useRealtimeData(
  opts: UseRealtimeDataOptions = {}
): UseRealtimeDataReturn {
  const { refreshMs = 3000, staleThresholdMs = 15000 } = opts;

  const [data, setData] = useState<SensorData | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(BACKOFF_INITIAL);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastMsgAtRef = useRef<number>(0);
  const connectingStartRef = useRef<number>(0);
  const mountedRef = useRef(true);

  const getWsUrl = useCallback(() => {
    const backendWs =
      process.env.NEXT_PUBLIC_BACKEND_WS_URL ??
      (typeof window !== "undefined"
        ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8080`
        : "ws://localhost:8080");
    return `${backendWs}/ws`;
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const closeWs = useCallback(() => {
    const ws = wsRef.current;
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    try { ws.close(); } catch {}
    wsRef.current = null;
  }, []);

  const scheduleReconnect = useCallback(() => {
    clearReconnectTimer();
    if (!mountedRef.current) return;
    if (!navigator.onLine) {
      setWsStatus("offline");
    } else {
      setWsStatus("disconnected");
    }
    reconnectTimerRef.current = setTimeout(() => {
      // connectWs will be defined later; use ref pattern
      connectRef.current?.();
    }, backoffRef.current);
    backoffRef.current = Math.min(backoffRef.current * 2, BACKOFF_MAX);
  }, [clearReconnectTimer]);

  // Use a ref to avoid stale closures in recursive reconnect
  const connectRef = useRef<(() => void) | null>(null);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    clearReconnectTimer();

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) return;
    if (ws && ws.readyState === WebSocket.CONNECTING) {
      if (Date.now() - connectingStartRef.current > 10000) {
        closeWs();
      } else {
        return;
      }
    }

    closeWs();
    setWsStatus("connecting");
    connectingStartRef.current = Date.now();

    const socket = new WebSocket(getWsUrl());
    wsRef.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current) { socket.close(); return; }
      backoffRef.current = BACKOFF_INITIAL;
      lastMsgAtRef.current = Date.now();
      setWsStatus("connected");
    };

    socket.onmessage = (event) => {
      if (!mountedRef.current) return;
      lastMsgAtRef.current = Date.now();
      try {
        const payload = JSON.parse(event.data);
        if (payload?.data) {
          setData(payload.data as SensorData);
          if (payload.data.timestamp_ms) {
            setLastUpdatedAt(Number(payload.data.timestamp_ms));
          }
        }
      } catch {}
    };

    socket.onerror = () => {
      if (!mountedRef.current) return;
      closeWs();
      scheduleReconnect();
    };

    socket.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      scheduleReconnect();
    };
  }, [clearReconnectTimer, closeWs, getWsUrl, scheduleReconnect]);

  // Keep connectRef up to date
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Stale connection watchdog
  useEffect(() => {
    staleTimerRef.current = setInterval(() => {
      const ws = wsRef.current;
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        connect();
        return;
      }
      if (ws.readyState === WebSocket.CONNECTING) {
        if (Date.now() - connectingStartRef.current > 10000) {
          closeWs();
          connect();
        }
        return;
      }
      if (
        ws.readyState === WebSocket.OPEN &&
        Date.now() - lastMsgAtRef.current > Math.max(staleThresholdMs, refreshMs * 4)
      ) {
        closeWs();
        connect();
      }
    }, 10000);

    return () => {
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
    };
  }, [connect, closeWs, refreshMs, staleThresholdMs]);

  // Network event listeners
  useEffect(() => {
    const onOffline = () => {
      closeWs();
      setWsStatus("offline");
    };
    const onOnline = () => {
      backoffRef.current = BACKOFF_INITIAL;
      connect();
    };
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, [connect, closeWs]);

  // Mount / unmount
  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearReconnectTimer();
      closeWs();
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
    };
  }, [connect, clearReconnectTimer, closeWs]);

  return { data, wsStatus, lastUpdatedAt };
}
