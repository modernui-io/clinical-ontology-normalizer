"use client";

import { cn } from "@/lib/utils";
import { ConnectionStatus as ConnectionStatusType } from "@/hooks/use-websocket";

interface ConnectionStatusProps {
  /** Current connection status */
  status: ConnectionStatusType;
  /** Whether to show the status label */
  showLabel?: boolean;
  /** Optional additional class names */
  className?: string;
}

/**
 * Small indicator showing WebSocket connection status.
 * - Green dot for connected
 * - Yellow/amber dot for connecting
 * - Red dot for disconnected
 *
 * @example
 * ```tsx
 * const { status } = useWebSocket();
 * return <ConnectionStatus status={status} showLabel />;
 * ```
 */
export function ConnectionStatus({
  status,
  showLabel = false,
  className,
}: ConnectionStatusProps) {
  const statusConfig = {
    connected: {
      color: "bg-green-500",
      pulseColor: "bg-green-400",
      label: "Connected",
      ariaLabel: "WebSocket connected",
    },
    connecting: {
      color: "bg-amber-500",
      pulseColor: "bg-amber-400",
      label: "Connecting...",
      ariaLabel: "WebSocket connecting",
    },
    disconnected: {
      color: "bg-red-500",
      pulseColor: "bg-red-400",
      label: "Disconnected",
      ariaLabel: "WebSocket disconnected",
    },
  };

  const config = statusConfig[status];

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      role="status"
      aria-label={config.ariaLabel}
    >
      <span className="relative flex h-2.5 w-2.5">
        {status === "connecting" && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              config.pulseColor
            )}
          />
        )}
        <span
          className={cn(
            "relative inline-flex h-2.5 w-2.5 rounded-full",
            config.color
          )}
        />
      </span>
      {showLabel && (
        <span className="text-xs text-muted-foreground">{config.label}</span>
      )}
    </div>
  );
}
