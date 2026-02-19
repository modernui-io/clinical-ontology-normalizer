"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
  ChevronDown,
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
  ShieldCheck,
  Database,
  Workflow,
  Gauge,
  Pill,
  FileCheck,
  Shuffle,
  FlaskConical,
  FileSpreadsheet,
  Syringe,
  Scale,
  Package,
  Microscope,
  Building2,
  Lock,
} from "lucide-react";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSubGroup {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: NavItem[];
}

interface NavSection {
  title: string;
  items?: NavItem[];
  subGroups?: NavSubGroup[];
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
    title: "Clinical Trials",
    subGroups: [
      {
        title: "Trial Operations",
        icon: ClipboardList,
        items: [
          { title: "Trials", href: "/trials", icon: ClipboardList },
          { title: "Sites", href: "/sites", icon: Server },
          { title: "Screening", href: "/trials/bulk-screen", icon: Shield },
          { title: "Enrollment", href: "/trials/dual-enrollment", icon: GitBranch },
          { title: "ROI Dashboard", href: "/roi-dashboard", icon: BarChart3 },
        ],
      },
      {
        title: "Safety & PV",
        icon: AlertTriangle,
        items: [
          { title: "Adverse Events", href: "/adverse-events", icon: AlertTriangle },
          { title: "Drug Safety", href: "/clinical/drug-safety", icon: Pill },
          { title: "Pharmacovigilance", href: "/pharmacovigilance", icon: Shield },
        ],
      },
      {
        title: "Regulatory",
        icon: FileCheck,
        items: [
          { title: "Submissions", href: "/regulatory", icon: FileCheck },
          { title: "eTMF", href: "/etmf", icon: FileText },
          { title: "IRB / DSMB", href: "/irb", icon: Scale },
        ],
      },
      {
        title: "Randomization",
        icon: Shuffle,
        items: [
          { title: "Schemes", href: "/randomization", icon: Shuffle },
          { title: "Unblinding", href: "/unblinding", icon: Lock },
        ],
      },
      {
        title: "Data Management",
        icon: FileSpreadsheet,
        items: [
          { title: "CRF Management", href: "/crf-management", icon: FileSpreadsheet },
          { title: "EDC Forms", href: "/edc", icon: ClipboardList },
          { title: "eConsent", href: "/econsent", icon: FileCheck },
        ],
      },
      {
        title: "Supply & Lab",
        icon: FlaskConical,
        items: [
          { title: "Drug Accountability", href: "/drug-accountability", icon: Pill },
          { title: "Lab Management", href: "/lab-management", icon: Microscope },
          { title: "Specimens", href: "/specimens", icon: FlaskConical },
        ],
      },
      {
        title: "Integrations",
        icon: Network,
        items: [
          { title: "Medidata Rave", href: "/integrations/medidata-rave", icon: Database },
          { title: "Veeva Vault", href: "/integrations/veeva-vault", icon: Database },
          { title: "HIE", href: "/metriport", icon: Network },
        ],
      },
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
      { title: "Datasets Hub", href: "/datasets", icon: Database },
      { title: "MIMIC Import", href: "/mimic", icon: Database },
      { title: "MTSamples", href: "/datasets/mtsamples", icon: FileSpreadsheet },
      { title: "Synthea", href: "/datasets/synthea", icon: Users },
      { title: "OpenEHR", href: "/pipelines/openehr", icon: Shuffle },
      { title: "OpenEHR Ops", href: "/pipelines/openehr/operations", icon: FileCheck },
      { title: "Data Sources", href: "/admin/data-sources", icon: Database },
      { title: "Data Quality", href: "/pipelines/quality", icon: Gauge },
    ],
  },
  {
    title: "Research Lab",
    subGroups: [
      {
        title: "Experiments",
        icon: FlaskConical,
        items: [
          { title: "Dashboard", href: "/research", icon: LayoutDashboard },
          { title: "Experiments", href: "/research/experiments", icon: FlaskConical },
          { title: "Data Ingestion", href: "/research/ingest", icon: Database },
        ],
      },
      {
        title: "Analysis",
        icon: Microscope,
        items: [
          { title: "Note Browser", href: "/research/notes", icon: FileText },
          { title: "Pipeline Monitor", href: "/research/pipeline", icon: Workflow },
          { title: "Assertions", href: "/research/assertions", icon: Shield },
          { title: "OMOP Mapping", href: "/research/mapping", icon: Shuffle },
          { title: "KG Explorer", href: "/research/kg", icon: Network },
        ],
      },
      {
        title: "Results",
        icon: BarChart3,
        items: [
          { title: "Compare", href: "/research/compare", icon: GitBranch },
          { title: "Paper Figures", href: "/research/figures", icon: FileCheck },
        ],
      },
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
      { title: "Diagnostics", href: "/admin/diagnostics", icon: Activity },
      { title: "Audit Log", href: "/audit", icon: ClipboardList },
      { title: "Settings", href: "/settings", icon: Settings },
    ],
  },
  {
    title: "Enterprise Readiness",
    subGroups: [
      {
        title: "Trust & Evidence",
        icon: ShieldCheck,
        items: [
          { title: "Trust Center", href: "/trust", icon: ShieldCheck },
          { title: "Proof", href: "/proof", icon: FileCheck },
          { title: "Security", href: "/security", icon: Lock },
          { title: "Sales Demo", href: "/sales-demo", icon: Sparkles },
        ],
      },
      {
        title: "Docs & Reports",
        icon: FileText,
        items: [
          { title: "Documentation", href: "/docs", icon: BookOpen },
          { title: "Changelog", href: "/changelog", icon: ScrollText },
          { title: "Reports", href: "/reports", icon: BarChart3 },
          { title: "Report Export", href: "/reports/export", icon: FileCheck },
        ],
      },
    ],
  },
  {
    title: "Reference",
    items: [
      { title: "Glossary", href: "/glossary", icon: BookOpen },
    ],
  },
];

interface SidebarProps {
  className?: string;
}

// Pages that should not show the sidebar
const AUTH_PAGES = ["/login", "/register", "/forgot-password"];
const FULL_BLEED_PAGES = ["/", "/investors", "/contact", "/about", "/privacy", "/terms", "/security", "/careers", "/proof", "/changelog", "/docs", "/sales-demo"];
const isAuthPage = (pathname: string) => {
  return AUTH_PAGES.includes(pathname) || FULL_BLEED_PAGES.includes(pathname) || pathname.startsWith("/smart/");
};

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [openSubGroups, setOpenSubGroups] = useState<Record<string, boolean>>({});
  const desktopNavRef = useRef<HTMLElement>(null);
  const mobileNavRef = useRef<HTMLElement>(null);
  const savedScrollTop = useRef(0);

  // Save sidebar scroll position before navigation changes it
  const handleNavScroll = useCallback((e: React.UIEvent<HTMLElement>) => {
    savedScrollTop.current = e.currentTarget.scrollTop;
  }, []);

  // Restore sidebar scroll position after route change
  useEffect(() => {
    requestAnimationFrame(() => {
      if (desktopNavRef.current) {
        desktopNavRef.current.scrollTop = savedScrollTop.current;
      }
      if (mobileNavRef.current) {
        mobileNavRef.current.scrollTop = savedScrollTop.current;
      }
    });
  }, [pathname]);

  // Auto-open the subgroup that contains the current path
  useEffect(() => {
    for (const section of navSections) {
      if (section.subGroups) {
        for (const group of section.subGroups) {
          if (group.items.some((item) => pathname.startsWith(item.href))) {
            setOpenSubGroups((prev) => ({ ...prev, [group.title]: true }));
          }
        }
      }
    }
  }, [pathname]);

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

  const toggleSubGroup = (title: string) => {
    setOpenSubGroups((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  const NavLink = ({ item }: { item: NavItem }) => {
    const Icon = item.icon;
    const active = isActive(item.href);
    return (
      <li role="listitem">
        <Link
          href={item.href}
          scroll={false}
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
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {!isCollapsed && <span>{item.title}</span>}
        </Link>
      </li>
    );
  };

  const renderSidebarContent = (navRef: React.RefObject<HTMLElement | null>) => (
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
        ref={navRef}
        onScroll={handleNavScroll}
        className="flex-1 overflow-y-auto p-3"
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="space-y-5">
          {navSections.map((section) => {
            const sectionId = `nav-section-${section.title.toLowerCase().replace(/\s+/g, "-")}`;
            return (
              <div key={section.title} role="group" aria-labelledby={sectionId}>
                {!isCollapsed && (
                  <h3
                    id={sectionId}
                    className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {section.title}
                  </h3>
                )}

                {/* Regular items */}
                {section.items && (
                  <ul className="space-y-0.5" role="list">
                    {section.items.map((item) => (
                      <NavLink key={item.href} item={item} />
                    ))}
                  </ul>
                )}

                {/* Collapsible sub-groups */}
                {section.subGroups && !isCollapsed && (
                  <div className="space-y-0.5">
                    {section.subGroups.map((group) => {
                      const GroupIcon = group.icon;
                      const isOpen = openSubGroups[group.title] ?? false;
                      const hasActiveChild = group.items.some((item) =>
                        isActive(item.href)
                      );
                      return (
                        <Collapsible
                          key={group.title}
                          open={isOpen}
                          onOpenChange={() => toggleSubGroup(group.title)}
                        >
                          <CollapsibleTrigger asChild>
                            <button
                              className={cn(
                                "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                                hasActiveChild
                                  ? "text-sidebar-accent-foreground"
                                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                              )}
                            >
                              <GroupIcon className="h-4 w-4 shrink-0" />
                              <span className="flex-1 text-left">{group.title}</span>
                              <ChevronDown
                                className={cn(
                                  "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
                                  isOpen && "rotate-180"
                                )}
                              />
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <ul className="ml-4 mt-0.5 space-y-0.5 border-l border-border pl-2" role="list">
                              {group.items.map((item) => (
                                <NavLink key={item.href} item={item} />
                              ))}
                            </ul>
                          </CollapsibleContent>
                        </Collapsible>
                      );
                    })}
                  </div>
                )}

                {/* Collapsed mode: show sub-group items as flat icons */}
                {section.subGroups && isCollapsed && (
                  <ul className="space-y-0.5" role="list">
                    {section.subGroups.flatMap((group) =>
                      group.items.slice(0, 1).map((item) => (
                        <NavLink key={item.href} item={item} />
                      ))
                    )}
                  </ul>
                )}
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
        {renderSidebarContent(mobileNavRef)}
      </aside>

      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden h-screen border-r bg-sidebar transition-all duration-200 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:flex lg:flex-col",
          isCollapsed ? "lg:w-16" : "lg:w-60",
          className
        )}
        aria-label="Desktop navigation"
      >
        {renderSidebarContent(desktopNavRef)}
      </aside>

      {/* Spacer for main content */}
      <div
        className={cn(
          "hidden lg:block",
          isCollapsed ? "lg:w-16" : "lg:w-60"
        )}
        aria-hidden="true"
      />
    </>
  );
}
