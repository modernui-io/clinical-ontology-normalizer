"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  FileText,
  Users,
  Stethoscope,
  CreditCard,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Activity,
  ClipboardList,
  Calculator,
  Shield,
  BarChart3,
  Radio,
  Network,
  GitBranch,
  Route,
  AlertTriangle,
  Brain,
} from "lucide-react";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: { title: string; href: string }[];
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    title: "Data Management",
    items: [
      { title: "Documents", href: "/documents", icon: FileText },
      { title: "Patients", href: "/patients", icon: Users },
      { title: "Search", href: "/search", icon: Search },
    ],
  },
  {
    title: "Clinical",
    items: [
      { title: "Clinical Tools", href: "/clinical", icon: Stethoscope },
      { title: "Calculators", href: "/calculators", icon: Calculator },
      { title: "Quality Measures", href: "/quality", icon: Activity },
    ],
  },
  {
    title: "Analytics",
    items: [
      { title: "Risk Dashboard", href: "/analytics/risks", icon: AlertTriangle },
      { title: "Model Management", href: "/analytics/models", icon: Brain },
      { title: "Visualizations", href: "/analytics/visualizations", icon: BarChart3 },
      { title: "Real-time Streaming", href: "/analytics/streaming", icon: Radio },
      { title: "Knowledge Graph", href: "/analytics/graph", icon: Network },
      { title: "Patient Similarity", href: "/analytics/graph/patients", icon: GitBranch },
      { title: "Drug Pathways", href: "/analytics/graph/pathways", icon: Route },
    ],
  },
  {
    title: "Administration",
    items: [
      { title: "Billing", href: "/billing", icon: CreditCard },
      { title: "Audit Log", href: "/audit", icon: ClipboardList },
      { title: "Access Control", href: "/access", icon: Shield },
      { title: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  // Close mobile menu on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsMobileOpen(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/" || pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  const SidebarContent = () => (
    <div className="flex h-full flex-col">
      {/* Logo/Brand */}
      <div className="flex h-16 items-center border-b px-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Activity className="h-5 w-5" />
          </div>
          {!isCollapsed && (
            <span className="text-lg font-semibold">Clinical ONT</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4">
        <div className="space-y-6">
          {navSections.map((section) => (
            <div key={section.title}>
              {!isCollapsed && (
                <h3 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {section.title}
                </h3>
              )}
              <ul className="space-y-1">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                          isCollapsed && "justify-center px-2"
                        )}
                        title={isCollapsed ? item.title : undefined}
                      >
                        <Icon className="h-5 w-5 shrink-0" />
                        {!isCollapsed && <span>{item.title}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>

      {/* Collapse Toggle - Desktop only */}
      <div className="hidden border-t p-4 lg:block">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="ml-2">Collapse</span>
            </>
          )}
        </Button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed left-4 top-4 z-50 lg:hidden"
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        aria-label={isMobileOpen ? "Close menu" : "Open menu"}
      >
        {isMobileOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <Menu className="h-5 w-5" />
        )}
      </Button>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 transform bg-sidebar transition-transform duration-200 ease-in-out lg:hidden",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <SidebarContent />
      </aside>

      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden h-screen border-r bg-sidebar transition-all duration-200 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:flex lg:flex-col",
          isCollapsed ? "lg:w-16" : "lg:w-64",
          className
        )}
      >
        <SidebarContent />
      </aside>

      {/* Spacer for main content */}
      <div
        className={cn(
          "hidden lg:block",
          isCollapsed ? "lg:w-16" : "lg:w-64"
        )}
      />
    </>
  );
}
