"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Notifications } from "@/components/Notifications";
import {
  Bell,
  ChevronDown,
  LogOut,
  Settings,
  User,
  Moon,
  Sun,
  Wifi,
} from "lucide-react";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Mock notifications
  const notifications = [
    {
      id: "1",
      title: "Document processed",
      message: "Patient discharge summary completed",
      time: "5 min ago",
      read: false,
    },
    {
      id: "2",
      title: "New patient added",
      message: "John Doe has been added to the system",
      time: "1 hour ago",
      read: false,
    },
    {
      id: "3",
      title: "Quality alert",
      message: "Missing diagnosis code detected",
      time: "2 hours ago",
      read: true,
    },
  ];

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
    >
      {/* Left side - Page title area (placeholder for breadcrumbs or title) */}
      <div className="flex items-center gap-4 lg:pl-0 pl-12">
        <h2 className="text-lg font-semibold text-foreground">
          Clinical Ontology Normalizer
        </h2>
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-2">
        {/* WebSocket Connection Status */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50">
          <Wifi className="h-3.5 w-3.5 text-muted-foreground" />
          <Notifications showConnectionStatus showConnectionLabel={false} />
        </div>

        {/* Dark mode toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleDarkMode}
          aria-label="Toggle dark mode"
        >
          {isDarkMode ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
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
            aria-label="Notifications"
            className="relative"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-white">
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
              />
              <div className="absolute right-0 top-full z-20 mt-2 w-80 rounded-lg border bg-popover p-0 shadow-lg">
                <div className="border-b p-4">
                  <h3 className="font-semibold">Notifications</h3>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-sm text-muted-foreground">
                      No notifications
                    </div>
                  ) : (
                    <ul>
                      {notifications.map((notification) => (
                        <li
                          key={notification.id}
                          className={cn(
                            "border-b p-4 last:border-0",
                            !notification.read && "bg-muted/50"
                          )}
                        >
                          <div className="flex items-start gap-3">
                            <div
                              className={cn(
                                "mt-1 h-2 w-2 shrink-0 rounded-full",
                                notification.read ? "bg-transparent" : "bg-primary"
                              )}
                            />
                            <div className="flex-1 space-y-1">
                              <p className="text-sm font-medium">
                                {notification.title}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {notification.message}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {notification.time}
                              </p>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="border-t p-2">
                  <Button variant="ghost" size="sm" className="w-full">
                    View all notifications
                  </Button>
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
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
              <User className="h-4 w-4" />
            </div>
            <span className="hidden text-sm font-medium md:inline-block">
              Demo User
            </span>
            <ChevronDown className="h-4 w-4" />
          </Button>

          {/* User Dropdown */}
          {isUserMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsUserMenuOpen(false)}
              />
              <div className="absolute right-0 top-full z-20 mt-2 w-56 rounded-lg border bg-popover p-1 shadow-lg">
                <div className="border-b p-3">
                  <p className="font-medium">Demo User</p>
                  <p className="text-xs text-muted-foreground">
                    demo@clinicalont.local
                  </p>
                </div>
                <div className="p-1">
                  <Link
                    href="/settings/profile"
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent"
                    onClick={() => setIsUserMenuOpen(false)}
                  >
                    <User className="h-4 w-4" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent"
                    onClick={() => setIsUserMenuOpen(false)}
                  >
                    <Settings className="h-4 w-4" />
                    Settings
                  </Link>
                </div>
                <div className="border-t p-1">
                  <button
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-accent"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      // Handle logout
                    }}
                  >
                    <LogOut className="h-4 w-4" />
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
