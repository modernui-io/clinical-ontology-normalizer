"use client";

import { useCallback, useEffect } from "react";
import { toast } from "sonner";
import {
  useWebSocket,
  NotificationData,
  JobStartedData,
  JobCompletedData,
  JobFailedData,
  WebSocketEventHandlers,
} from "@/hooks/use-websocket";
import { ConnectionStatus } from "@/components/ConnectionStatus";

interface NotificationsProps {
  /** Whether to show connection status indicator */
  showConnectionStatus?: boolean;
  /** Whether to show the connection status label */
  showConnectionLabel?: boolean;
  /** Whether to show job started notifications */
  showJobStarted?: boolean;
  /** Whether to show job completed notifications */
  showJobCompleted?: boolean;
  /** Whether to show job failed notifications */
  showJobFailed?: boolean;
  /** Auto-dismiss duration for success notifications (in ms) */
  successDuration?: number;
  /** Auto-dismiss duration for error notifications (in ms) */
  errorDuration?: number;
  /** Auto-dismiss duration for info notifications (in ms) */
  infoDuration?: number;
  /** Auto-dismiss duration for warning notifications (in ms) */
  warningDuration?: number;
  /** Custom class name for the connection status */
  className?: string;
  /** Callback when a notification is received */
  onNotification?: (notification: NotificationData) => void;
  /** Callback when connection status changes */
  onConnectionChange?: (isConnected: boolean) => void;
}

/**
 * Notifications component that connects to the WebSocket server
 * and displays toast-style notifications for real-time events.
 *
 * Features:
 * - Toast-style notifications from WebSocket events
 * - Different styles for success, error, info, warning
 * - Auto-dismiss after configurable timeout
 * - Click to dismiss
 * - Optional connection status indicator
 *
 * @example
 * ```tsx
 * // In your layout or app component
 * import { Notifications } from "@/components/Notifications";
 * import { Toaster } from "@/components/ui/sonner";
 *
 * export default function Layout({ children }) {
 *   return (
 *     <>
 *       <Notifications showConnectionStatus />
 *       {children}
 *       <Toaster />
 *     </>
 *   );
 * }
 * ```
 */
export function Notifications({
  showConnectionStatus = false,
  showConnectionLabel = false,
  showJobStarted = true,
  showJobCompleted = true,
  showJobFailed = true,
  successDuration = 4000,
  errorDuration = 6000,
  infoDuration = 4000,
  warningDuration = 5000,
  className,
  onNotification,
  onConnectionChange,
}: NotificationsProps) {
  const handleNotification = useCallback(
    (data: NotificationData) => {
      const { title, message, notification_type } = data;

      const options = {
        description: message,
        closeButton: true,
      };

      switch (notification_type) {
        case "success":
          toast.success(title, { ...options, duration: successDuration });
          break;
        case "error":
          toast.error(title, { ...options, duration: errorDuration });
          break;
        case "warning":
          toast.warning(title, { ...options, duration: warningDuration });
          break;
        case "info":
        default:
          toast.info(title, { ...options, duration: infoDuration });
          break;
      }

      onNotification?.(data);
    },
    [successDuration, errorDuration, infoDuration, warningDuration, onNotification]
  );

  const handleJobStarted = useCallback(
    (data: JobStartedData) => {
      if (showJobStarted) {
        toast.info("Job Started", {
          description: `Processing ${data.total_items} items (${data.job_type})`,
          duration: infoDuration,
          closeButton: true,
        });
      }
    },
    [showJobStarted, infoDuration]
  );

  const handleJobCompleted = useCallback(
    (data: JobCompletedData) => {
      if (showJobCompleted) {
        const durationSec = (data.duration_ms / 1000).toFixed(1);
        const hasFailures = data.failed_count > 0;

        if (hasFailures) {
          toast.warning("Job Completed with Errors", {
            description: `${data.successful_count}/${data.total_items} successful, ${data.failed_count} failed (${durationSec}s)`,
            duration: warningDuration,
            closeButton: true,
          });
        } else {
          toast.success("Job Completed", {
            description: `${data.successful_count} items processed in ${durationSec}s`,
            duration: successDuration,
            closeButton: true,
          });
        }
      }
    },
    [showJobCompleted, successDuration, warningDuration]
  );

  const handleJobFailed = useCallback(
    (data: JobFailedData) => {
      if (showJobFailed) {
        toast.error("Job Failed", {
          description: data.error_message,
          duration: errorDuration,
          closeButton: true,
        });
      }
    },
    [showJobFailed, errorDuration]
  );

  const handlers: WebSocketEventHandlers = {
    onNotification: handleNotification,
    onJobStarted: handleJobStarted,
    onJobCompleted: handleJobCompleted,
    onJobFailed: handleJobFailed,
  };

  const { status, isConnected } = useWebSocket({
    handlers,
  });

  // Notify parent of connection changes
  useEffect(() => {
    onConnectionChange?.(isConnected);
  }, [isConnected, onConnectionChange]);

  if (!showConnectionStatus) {
    return null;
  }

  return (
    <ConnectionStatus
      status={status}
      showLabel={showConnectionLabel}
      className={className}
    />
  );
}

/**
 * Hook version of Notifications for use in contexts where you need
 * both the WebSocket connection and notification handling.
 *
 * @example
 * ```tsx
 * const { status, subscribeToJob } = useNotifications({
 *   onNotification: (notification) => {
 *     console.log('Received notification:', notification);
 *   },
 * });
 *
 * // Subscribe to a specific job
 * subscribeToJob('job-uuid-123');
 * ```
 */
export function useNotifications(options: Omit<NotificationsProps, "className" | "showConnectionStatus" | "showConnectionLabel"> = {}) {
  const {
    showJobStarted = true,
    showJobCompleted = true,
    showJobFailed = true,
    successDuration = 4000,
    errorDuration = 6000,
    infoDuration = 4000,
    warningDuration = 5000,
    onNotification,
    onConnectionChange,
  } = options;

  const handleNotification = useCallback(
    (data: NotificationData) => {
      const { title, message, notification_type } = data;

      const toastOptions = {
        description: message,
        closeButton: true,
      };

      switch (notification_type) {
        case "success":
          toast.success(title, { ...toastOptions, duration: successDuration });
          break;
        case "error":
          toast.error(title, { ...toastOptions, duration: errorDuration });
          break;
        case "warning":
          toast.warning(title, { ...toastOptions, duration: warningDuration });
          break;
        case "info":
        default:
          toast.info(title, { ...toastOptions, duration: infoDuration });
          break;
      }

      onNotification?.(data);
    },
    [successDuration, errorDuration, infoDuration, warningDuration, onNotification]
  );

  const handleJobStarted = useCallback(
    (data: JobStartedData) => {
      if (showJobStarted) {
        toast.info("Job Started", {
          description: `Processing ${data.total_items} items (${data.job_type})`,
          duration: infoDuration,
          closeButton: true,
        });
      }
    },
    [showJobStarted, infoDuration]
  );

  const handleJobCompleted = useCallback(
    (data: JobCompletedData) => {
      if (showJobCompleted) {
        const durationSec = (data.duration_ms / 1000).toFixed(1);
        const hasFailures = data.failed_count > 0;

        if (hasFailures) {
          toast.warning("Job Completed with Errors", {
            description: `${data.successful_count}/${data.total_items} successful, ${data.failed_count} failed (${durationSec}s)`,
            duration: warningDuration,
            closeButton: true,
          });
        } else {
          toast.success("Job Completed", {
            description: `${data.successful_count} items processed in ${durationSec}s`,
            duration: successDuration,
            closeButton: true,
          });
        }
      }
    },
    [showJobCompleted, successDuration, warningDuration]
  );

  const handleJobFailed = useCallback(
    (data: JobFailedData) => {
      if (showJobFailed) {
        toast.error("Job Failed", {
          description: data.error_message,
          duration: errorDuration,
          closeButton: true,
        });
      }
    },
    [showJobFailed, errorDuration]
  );

  const handlers: WebSocketEventHandlers = {
    onNotification: handleNotification,
    onJobStarted: handleJobStarted,
    onJobCompleted: handleJobCompleted,
    onJobFailed: handleJobFailed,
  };

  const wsResult = useWebSocket({ handlers });

  // Notify parent of connection changes
  useEffect(() => {
    onConnectionChange?.(wsResult.isConnected);
  }, [wsResult.isConnected, onConnectionChange]);

  return wsResult;
}
