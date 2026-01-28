"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * WebSocket connection status
 */
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/**
 * WebSocket event types received from the server
 */
export type WebSocketEventType =
  | "connected"
  | "ping"
  | "pong"
  | "subscribed"
  | "unsubscribed"
  | "job_started"
  | "job_progress"
  | "job_completed"
  | "job_failed"
  | "notification";

/**
 * Base interface for all WebSocket messages
 */
export interface WebSocketMessage {
  type: WebSocketEventType;
  timestamp: string;
  data?: Record<string, unknown>;
}

/**
 * Job started event data
 */
export interface JobStartedData {
  job_id: string;
  total_items: number;
  job_type: string;
}

/**
 * Job progress event data
 */
export interface JobProgressData {
  job_id: string;
  processed_count: number;
  total_count: number;
  progress_percent: number;
  current_item?: string;
}

/**
 * Job completed event data
 */
export interface JobCompletedData {
  job_id: string;
  total_items: number;
  successful_count: number;
  failed_count: number;
  duration_ms: number;
}

/**
 * Job failed event data
 */
export interface JobFailedData {
  job_id: string;
  error_message: string;
  error_code?: string;
}

/**
 * Notification event data
 */
export interface NotificationData {
  title: string;
  message: string;
  notification_type: "success" | "error" | "info" | "warning";
  job_id?: string;
}

/**
 * Event handlers for WebSocket messages
 */
export interface WebSocketEventHandlers {
  onConnected?: () => void;
  onDisconnected?: () => void;
  onJobStarted?: (data: JobStartedData) => void;
  onJobProgress?: (data: JobProgressData) => void;
  onJobCompleted?: (data: JobCompletedData) => void;
  onJobFailed?: (data: JobFailedData) => void;
  onNotification?: (data: NotificationData) => void;
  onMessage?: (message: WebSocketMessage) => void;
}

/**
 * Options for the WebSocket hook
 */
export interface UseWebSocketOptions {
  /** URL of the WebSocket server (defaults to ws://localhost:8000/ws) */
  url?: string;
  /** Whether to automatically connect on mount (defaults to true) */
  autoConnect?: boolean;
  /** Whether to automatically reconnect on disconnect (defaults to true) */
  autoReconnect?: boolean;
  /** Initial reconnect delay in ms (defaults to 1000) */
  reconnectDelay?: number;
  /** Maximum reconnect delay in ms (defaults to 30000) */
  maxReconnectDelay?: number;
  /** Reconnect delay multiplier for exponential backoff (defaults to 2) */
  reconnectMultiplier?: number;
  /** Maximum number of reconnect attempts (defaults to Infinity) */
  maxReconnectAttempts?: number;
  /** Event handlers */
  handlers?: WebSocketEventHandlers;
}

/**
 * Return type of the useWebSocket hook
 */
export interface UseWebSocketReturn {
  /** Current connection status */
  status: ConnectionStatus;
  /** Whether currently connected */
  isConnected: boolean;
  /** Connect to the WebSocket server */
  connect: () => void;
  /** Disconnect from the WebSocket server */
  disconnect: () => void;
  /** Subscribe to a specific job's updates */
  subscribeToJob: (jobId: string) => void;
  /** Unsubscribe from a job's updates */
  unsubscribeFromJob: (jobId: string) => void;
  /** Send a ping to the server */
  ping: () => void;
  /** List of currently subscribed job IDs */
  subscribedJobs: string[];
  /** Number of reconnect attempts made */
  reconnectAttempts: number;
}

const DEFAULT_WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/api/v1/ws`
    : "ws://localhost:8000/api/v1/ws";

/**
 * React hook for managing a WebSocket connection with auto-reconnect,
 * exponential backoff, and typed event handlers.
 *
 * @example
 * ```tsx
 * const { status, subscribeToJob, isConnected } = useWebSocket({
 *   handlers: {
 *     onJobProgress: (data) => {
 *       console.log(`Job ${data.job_id}: ${data.progress_percent}%`);
 *     },
 *     onNotification: (data) => {
 *       toast[data.notification_type](data.message);
 *     },
 *   },
 * });
 * ```
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = DEFAULT_WS_URL,
    autoConnect = true,
    autoReconnect = true,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    reconnectMultiplier = 2,
    maxReconnectAttempts = Infinity,
    handlers = {},
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [subscribedJobs, setSubscribedJobs] = useState<string[]>([]);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentDelayRef = useRef(reconnectDelay);
  const shouldReconnectRef = useRef(autoReconnect);
  const handlersRef = useRef(handlers);

  // Keep handlers ref up to date
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      const h = handlersRef.current;

      // Call the generic message handler if provided
      h.onMessage?.(message);

      // Handle specific message types
      switch (message.type) {
        case "connected":
          h.onConnected?.();
          break;

        case "job_started":
          if (message.data) {
            h.onJobStarted?.(message.data as unknown as JobStartedData);
          }
          break;

        case "job_progress":
          if (message.data) {
            h.onJobProgress?.(message.data as unknown as JobProgressData);
          }
          break;

        case "job_completed":
          if (message.data) {
            h.onJobCompleted?.(message.data as unknown as JobCompletedData);
          }
          break;

        case "job_failed":
          if (message.data) {
            h.onJobFailed?.(message.data as unknown as JobFailedData);
          }
          break;

        case "notification":
          if (message.data) {
            h.onNotification?.(message.data as unknown as NotificationData);
          }
          break;

        case "subscribed":
          // Update subscribed jobs list
          if (message.data?.job_id) {
            setSubscribedJobs((prev) => {
              const jobId = message.data!.job_id as string;
              if (!prev.includes(jobId)) {
                return [...prev, jobId];
              }
              return prev;
            });
          }
          break;

        case "unsubscribed":
          // Update subscribed jobs list
          if (message.data?.job_id) {
            setSubscribedJobs((prev) =>
              prev.filter((id) => id !== message.data!.job_id)
            );
          }
          break;

        case "ping":
        case "pong":
          // Heartbeat messages, no action needed
          break;
      }
    } catch (error) {
      console.error("Failed to parse WebSocket message:", error);
    }
  }, []);

  const connect = useCallback(() => {
    // Don't connect if already connecting or connected
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Clear any pending reconnect
    clearReconnectTimeout();

    setStatus("connecting");

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        setReconnectAttempts(0);
        currentDelayRef.current = reconnectDelay;
        shouldReconnectRef.current = autoReconnect;
      };

      ws.onclose = () => {
        setStatus("disconnected");
        handlersRef.current.onDisconnected?.();
        wsRef.current = null;

        // Schedule reconnect if enabled
        if (shouldReconnectRef.current && reconnectAttempts < maxReconnectAttempts) {
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts((prev) => prev + 1);
            // Exponential backoff
            currentDelayRef.current = Math.min(
              currentDelayRef.current * reconnectMultiplier,
              maxReconnectDelay
            );
            connect();
          }, currentDelayRef.current);
        }
      };

      ws.onerror = () => {
        // Non-fatal: connection will auto-reconnect
        console.warn("WebSocket connection error — will retry");
      };

      ws.onmessage = handleMessage;
    } catch (error) {
      console.warn("Failed to create WebSocket connection:", error);
      setStatus("disconnected");
    }
  }, [
    url,
    reconnectDelay,
    maxReconnectDelay,
    reconnectMultiplier,
    maxReconnectAttempts,
    autoReconnect,
    reconnectAttempts,
    handleMessage,
    clearReconnectTimeout,
  ]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimeout();

    if (wsRef.current) {
      // Send close message before disconnecting
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "close" }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("disconnected");
    setSubscribedJobs([]);
  }, [clearReconnectTimeout]);

  const subscribeToJob = useCallback((jobId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "subscribe", job_id: jobId }));
    }
  }, []);

  const unsubscribeFromJob = useCallback((jobId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "unsubscribe", job_id: jobId }));
    }
    setSubscribedJobs((prev) => prev.filter((id) => id !== jobId));
  }, []);

  const ping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "ping" }));
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      shouldReconnectRef.current = false;
      clearReconnectTimeout();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [autoConnect, connect, clearReconnectTimeout]);

  return {
    status,
    isConnected: status === "connected",
    connect,
    disconnect,
    subscribeToJob,
    unsubscribeFromJob,
    ping,
    subscribedJobs,
    reconnectAttempts,
  };
}
