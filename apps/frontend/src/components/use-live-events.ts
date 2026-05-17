"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth-store";

function getWsBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (configured) return configured;
  if (typeof window !== "undefined") {
    if (window.location.hostname === "localhost" && window.location.port === "3000") {
      return "ws://localhost:8080";
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }
  return "ws://localhost:8080";
}

export function useLiveEvents() {
  const token = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!token) return;
    // Token is NOT placed in the URL to avoid it appearing in server access logs.
    // Instead it is sent as the first message after the connection is established.
    const socket = new WebSocket(`${getWsBaseUrl()}/api/v1/ws`);
    // Register heartbeat immediately so the ref is always populated,
    // then clear it on any close (auth failure 4401, server drop, unmount).
    // Without this, a 4401 close leaves the interval firing against a dead socket.
    const heartbeat = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" }));
    }, 25_000);

    const cleanup = () => {
      window.clearInterval(heartbeat);
      socket.close();
    };

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }));
    };
    socket.onclose = () => {
      // Clear the heartbeat as soon as the socket closes for any reason
      // (auth failure code 4401, server disconnect, network drop).
      window.clearInterval(heartbeat);
    };
    socket.onmessage = (event) => {
      let payload: { type?: string };
      try {
        payload = JSON.parse(event.data) as { type?: string };
      } catch {
        // Malformed frame (e.g. partial write during a rolling restart) —
        // log and skip rather than letting the exception propagate and
        // potentially unmount the component via an uncaught error boundary.
        console.warn("[useLiveEvents] Received non-JSON WebSocket frame:", event.data);
        return;
      }
      if (payload.type?.startsWith("incident") || payload.type === "log.ingested") {
        queryClient.invalidateQueries({ queryKey: ["incidents"] });
        queryClient.invalidateQueries({ queryKey: ["analytics"] });
      }
      if (payload.type?.startsWith("notification")) {
        queryClient.invalidateQueries({ queryKey: ["notifications"] });
      }
    };
    return cleanup;
  }, [queryClient, token]);
}
