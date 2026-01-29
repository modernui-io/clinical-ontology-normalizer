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
  UserCog,
  Key,
  Server,
  Sparkles,
  Bot,
  BookOpen,
  ScrollText,
  Database,
  Workflow,
  Gauge,
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
      { title: "Vocabularies", href: "/vocabularies", icon: BookOpen },
    ],
  },
  {
    title: "Clinical",
    items: [
      { title: "Clinical Tools", href: "/clinical", icon: Stethoscope },
      { title: "Calculators", href: "/clinical/calculators", icon: Calculator },
      { title: "Guidelines", href: "/guidelines", icon: BookOpen },
      { title: "Policies", href: "/policies", icon: ScrollText },
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
    title: "AI/ML",
    items: [
      { title: "NLP Workbench", href: "/nlp", icon: Brain },
      { title: "AI Auto-Coding", href: "/ai-coding", icon: CreditCard },
      { title: "Clinical Intelligence", href: "/clinical/intelligence", icon: Sparkles },
      { title: "AI Assistant", href: "/assistant", icon: Bot },
      { title: "LLM Fine-tuning", href: "/llm/finetuning", icon: Sparkles },
    ],
  },
  {
    title: "Data Pipeline",
    items: [
      { title: "Pipelines", href: "/pipelines", icon: Workflow },
      { title: "Data Sources", href: "/admin/data-sources", icon: Database },
      { title: "Data Quality", href: "/pipelines/quality", icon: Gauge },
    ],
  },
  {
    title: "Administration",
    items: [
      { title: "Admin Dashboard", href: "/admin/dashboard", icon: Server },
      { title: "Users", href: "/admin/users", icon: UserCog },
      { title: "Roles", href: "/admin/roles", icon: Key },
      { title: "Access Control", href: "/admin/access", icon: Shield },
      { title: "SMART Apps", href: "/admin/smart-apps", icon: Key },
      { title: "Billing", href: "/billing", icon: CreditCard },
      { title: "Audit Log", href: "/audit", icon: ClipboardList },
      { title: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  className?: string;
}

// Pages that should not show the sidebar
const AUTH_PAGES = ["/login", "/register", "/forgot-password"];
const isAuthPage = (pathname: string) => {
  return AUTH_PAGES.includes(pathname) || pathname.startsWith("/smart/");
};

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

  // Don't render sidebar on auth pages (must be after all hooks)
  if (isAuthPage(pathname)) {
    return null;
  }

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
        <Link
          href="/dashboard"
          className="flex items-center gap-2"
          aria-label="Clinical ONT - Go to dashboard"
        >
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"
            aria-hidden="true"
          >
            <Activity className="h-5 w-5" />
          </div>
          {!isCollapsed && (
            <span className="text-lg font-semibold">Clinical ONT</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav
        className="flex-1 overflow-y-auto p-4"
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="space-y-6">
          {navSections.map((section) => {
            const sectionId = `nav-section-${section.title.toLowerCase().replace(/\s+/g, "-")}`;
            return (
              <div key={section.title} role="group" aria-labelledby={sectionId}>
                {!isCollapsed && (
                  <h3
                    id={sectionId}
                    className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {section.title}
                  </h3>
                )}
                <ul className="space-y-1" role="list">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                      <li key={item.href} role="listitem">
                        <Link
                          href={item.href}
                          className={cn(
                            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                            active
                              ? "bg-sidebar-accent text-sidebar-accent-foreground"
                              : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                            isCollapsed && "justify-center px-2"
                          )}
                          title={isCollapsed ? item.title : undefined}
                          aria-current={active ? "page" : undefined}
                          aria-label={isCollapsed ? item.title : undefined}
                        >
                          <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                          {!isCollapsed && <span>{item.title}</span>}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      </nav>

      {/* Collapse Toggle - Desktop only */}
      <div className="hidden border-t p-4 lg:block">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center"
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!isCollapsed}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
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
        aria-label={isMobileOpen ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={isMobileOpen}
        aria-controls="mobile-sidebar"
      >
        {isMobileOpen ? (
          <X className="h-5 w-5" aria-hidden="true" />
        ) : (
          <Menu className="h-5 w-5" aria-hidden="true" />
        )}
      </Button>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
          role="presentation"
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        id="mobile-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 transform bg-sidebar transition-transform duration-200 ease-in-out lg:hidden",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Mobile navigation"
        aria-hidden={!isMobileOpen}
        {...(!isMobileOpen && { inert: true })}
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
        aria-label="Desktop navigation"
      >
        <SidebarContent />
      </aside>

      {/* Spacer for main content */}
      <div
        className={cn(
          "hidden lg:block",
          isCollapsed ? "lg:w-16" : "lg:w-64"
        )}
        aria-hidden="true"
      />
    </>
  );
}
