"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Notifications } from "@/components/Notifications";
import { Breadcrumb } from "@/components/Breadcrumb";
import {
  Bell,
  ChevronDown,
  LogOut,
  Settings,
  User,
  Moon,
  Sun,
  Check,
  CheckCheck,
  AlertTriangle,
  Info,
  AlertCircle,
  Loader2,
} from "lucide-react";

interface HeaderProps {
  className?: string;
}

interface Notification {
  id: string;
  type: "critical" | "warning" | "info" | "success";
  title: string;
  message: string;
  created_at: string;
  read: boolean;
  channel?: string;
  metadata?: Record<string, unknown>;
}

// Format relative time
const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
};

// Get notification icon based on type
const getNotificationIcon = (type: Notification["type"]) => {
  switch (type) {
    case "critical":
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case "success":
      return <Check className="h-4 w-4 text-green-500" />;
    case "info":
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
};

// Pages that should not show the header
const AUTH_PAGES = ["/login", "/register", "/forgot-password"];
const FULL_BLEED_PAGES = ["/", "/investors"];
const isAuthPage = (pathname: string) => {
  return AUTH_PAGES.includes(pathname) || FULL_BLEED_PAGES.includes(pathname) || pathname.startsWith("/smart/");
};

export function Header({ className }: HeaderProps) {
  const pathname = usePathname();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isMarkingRead, setIsMarkingRead] = useState(false);

  // Fetch notifications from API (falls back to mock data if backend unavailable)
  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      const response = await fetch(
        "http://localhost:8000/api/v1/notifications?user_id=demo-user&limit=10",
        { signal: controller.signal }
      );
      clearTimeout(timeout);
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.notifications || []);
        setIsLoading(false);
        return;
      }
    } catch {
      // Backend unavailable — use mock data silently
    }
    setNotifications([
      {
        id: "1",
        type: "warning",
        title: "Drug Interaction Alert",
        message: "Potential interaction detected between metformin and contrast dye",
        created_at: new Date(Date.now() - 5 * 60000).toISOString(),
        read: false,
      },
      {
        id: "2",
        type: "info",
        title: "Document Processed",
        message: "Patient discharge summary completed successfully",
        created_at: new Date(Date.now() - 60 * 60000).toISOString(),
        read: false,
      },
      {
        id: "3",
        type: "critical",
        title: "Quality Alert",
        message: "Missing diagnosis code detected for billing",
        created_at: new Date(Date.now() - 2 * 60 * 60000).toISOString(),
        read: true,
      },
    ]);
    setIsLoading(false);
  }, []);

  // Fetch notifications on mount and when dropdown opens
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Don't render header on auth pages (must be after all hooks)
  if (isAuthPage(pathname)) {
    return null;
  }

  // Mark single notification as read
  const markAsRead = async (notificationId: string) => {
    try {
      await fetch("http://localhost:8000/api/v1/notifications/mark-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "demo-user",
          notification_ids: [notificationId],
        }),
      });
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
      );
    } catch {
      // Backend unavailable — optimistic update
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
      );
    }
  };

  // Mark all notifications as read
  const markAllAsRead = async () => {
    const unreadIds = notifications.filter((n) => !n.read).map((n) => n.id);
    if (unreadIds.length === 0) return;

    try {
      setIsMarkingRead(true);
      await fetch("http://localhost:8000/api/v1/notifications/mark-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "demo-user",
          notification_ids: unreadIds,
        }),
      });
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch {
      // Backend unavailable — optimistic update
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } finally {
      setIsMarkingRead(false);
    }
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
    document.documentElement.classList.toggle("dark");
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background px-4 lg:px-6",
        className
      )}
      role="banner"
    >
      {/* Left side - Breadcrumb navigation */}
      <div className="flex items-center gap-4 lg:pl-0 pl-12">
        <Breadcrumb maxLength={25} />
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-2" role="toolbar" aria-label="Header actions">
        {/* WebSocket Connection Status — hidden when backend unavailable */}
        <Notifications showConnectionStatus showConnectionLabel={false} />

        {/* Dark mode toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleDarkMode}
          aria-label={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          aria-pressed={isDarkMode}
        >
          {isDarkMode ? (
            <Sun className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Moon className="h-5 w-5" aria-hidden="true" />
          )}
        </Button>

        {/* Notifications */}
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setIsNotificationsOpen(!isNotificationsOpen);
              setIsUserMenuOpen(false);
            }}
            aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
            aria-expanded={isNotificationsOpen}
            aria-haspopup="dialog"
            aria-controls="notifications-panel"
            className="relative"
          >
            <Bell className="h-5 w-5" aria-hidden="true" />
            {unreadCount > 0 && (
              <span
                className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-white"
                aria-hidden="true"
              >
                {unreadCount}
              </span>
            )}
          </Button>

          {/* Notifications Dropdown */}
          {isNotificationsOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsNotificationsOpen(false)}
                aria-hidden="true"
                role="presentation"
              />
              <div
                id="notifications-panel"
                className="absolute right-0 top-full z-20 mt-2 w-96 rounded-lg border bg-popover p-0 shadow-lg"
                role="dialog"
                aria-label="Notifications panel"
                aria-modal="false"
              >
                <div className="flex items-center justify-between border-b p-4">
                  <div className="flex items-center gap-2">
                    <h3 id="notifications-heading" className="font-semibold">
                      Notifications
                    </h3>
                    {unreadCount > 0 && (
                      <Badge variant="secondary" className="text-xs" aria-label={`${unreadCount} new notifications`}>
                        {unreadCount} new
                      </Badge>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-7"
                      onClick={markAllAsRead}
                      disabled={isMarkingRead}
                      aria-label="Mark all notifications as read"
                    >
                      {isMarkingRead ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1" aria-hidden="true" />
                      ) : (
                        <CheckCheck className="h-3 w-3 mr-1" aria-hidden="true" />
                      )}
                      Mark all read
                    </Button>
                  )}
                </div>
                <div
                  className="max-h-96 overflow-y-auto"
                  role="region"
                  aria-labelledby="notifications-heading"
                  tabIndex={0}
                >
                  {isLoading ? (
                    <div className="p-8 text-center" role="status" aria-live="polite">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" aria-hidden="true" />
                      <p className="text-sm text-muted-foreground mt-2">
                        Loading notifications...
                      </p>
                    </div>
                  ) : notifications.length === 0 ? (
                    <div className="p-8 text-center" role="status">
                      <Bell className="h-8 w-8 mx-auto text-muted-foreground/50" aria-hidden="true" />
                      <p className="text-sm text-muted-foreground mt-2">
                        No notifications yet
                      </p>
                      <p className="text-xs text-muted-foreground">
                        You&apos;ll see alerts and updates here
                      </p>
                    </div>
                  ) : (
                    <ul role="list" aria-label="Notification list">
                      {notifications.map((notification) => (
                        <li
                          key={notification.id}
                          className={cn(
                            "border-b p-4 last:border-0 cursor-pointer hover:bg-accent/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary",
                            !notification.read && "bg-muted/50"
                          )}
                          onClick={() => {
                            if (!notification.read) {
                              markAsRead(notification.id);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              if (!notification.read) {
                                markAsRead(notification.id);
                              }
                            }
                          }}
                          tabIndex={0}
                          role="button"
                          aria-label={`${notification.type} notification: ${notification.title}. ${notification.message}. ${formatRelativeTime(notification.created_at)}${!notification.read ? ". Unread" : ""}`}
                        >
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5 shrink-0" aria-hidden="true">
                              {getNotificationIcon(notification.type)}
                            </div>
                            <div className="flex-1 min-w-0 space-y-1">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-sm font-medium truncate">
                                  {notification.title}
                                </p>
                                {!notification.read && (
                                  <div
                                    className="h-2 w-2 shrink-0 rounded-full bg-primary"
                                    aria-hidden="true"
                                  />
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {notification.message}
                              </p>
                              <div className="flex items-center justify-between">
                                <p className="text-[10px] text-muted-foreground">
                                  {formatRelativeTime(notification.created_at)}
                                </p>
                                {notification.channel && (
                                  <Badge variant="outline" className="text-[10px] h-4">
                                    {notification.channel}
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="border-t p-2 flex gap-2">
                  <Link
                    href="/settings/notifications"
                    className="flex-1"
                    onClick={() => setIsNotificationsOpen(false)}
                  >
                    <Button variant="ghost" size="sm" className="w-full text-xs">
                      <Settings className="h-3 w-3 mr-1" aria-hidden="true" />
                      Settings
                    </Button>
                  </Link>
                  <Link
                    href="/notifications"
                    className="flex-1"
                    onClick={() => setIsNotificationsOpen(false)}
                  >
                    <Button variant="outline" size="sm" className="w-full text-xs">
                      View all notifications
                    </Button>
                  </Link>
                </div>
              </div>
            </>
          )}
        </div>

        {/* User Menu */}
        <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            className="flex items-center gap-2"
            onClick={() => {
              setIsUserMenuOpen(!isUserMenuOpen);
              setIsNotificationsOpen(false);
            }}
            aria-label="User menu for Demo User"
            aria-expanded={isUserMenuOpen}
            aria-haspopup="menu"
            aria-controls="user-menu"
          >
            <div
              className="flex h-8 w-8 items-center justify-center rounded-full bg-muted"
              aria-hidden="true"
            >
              <User className="h-4 w-4" />
            </div>
            <span className="hidden text-sm font-medium md:inline-block">
              Demo User
            </span>
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          </Button>

          {/* User Dropdown */}
          {isUserMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsUserMenuOpen(false)}
                aria-hidden="true"
                role="presentation"
              />
              <div
                id="user-menu"
                className="absolute right-0 top-full z-20 mt-2 w-56 rounded-lg border bg-popover p-1 shadow-lg"
                role="menu"
                aria-label="User menu"
              >
                <div className="border-b p-3" role="presentation">
                  <p className="font-medium">Demo User</p>
                  <p className="text-xs text-muted-foreground">
                    demo@clinicalont.local
                  </p>
                </div>
                <div className="p-1" role="group">
                  <Link
                    href="/settings/profile"
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    onClick={() => setIsUserMenuOpen(false)}
                    role="menuitem"
                  >
                    <User className="h-4 w-4" aria-hidden="true" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    onClick={() => setIsUserMenuOpen(false)}
                    role="menuitem"
                  >
                    <Settings className="h-4 w-4" aria-hidden="true" />
                    Settings
                  </Link>
                </div>
                <div className="border-t p-1" role="group">
                  <button
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      // Handle logout
                    }}
                    role="menuitem"
                    aria-label="Sign out of your account"
                  >
                    <LogOut className="h-4 w-4" aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
