"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Route name mappings for display
 * Maps route segments to human-readable names
 */
const routeNames: Record<string, string> = {
  dashboard: "Dashboard",
  patients: "Patients",
  documents: "Documents",
  upload: "Upload",
  search: "Search",
  clinical: "Clinical Tools",
  interactions: "Drug Interactions",
  tools: "Clinical Tools",
  billing: "Billing",
  coding: "Medical Coding",
  hcc: "HCC Coding",
  etl: "ETL Pipeline",
  sources: "Data Sources",
  pipelines: "Pipelines",
  new: "New",
  settings: "Settings",
  notifications: "Notifications",
  webhooks: "Webhooks",
  audit: "Audit Log",
  admin: "Admin",
  access: "Access Control",
  valuesets: "Value Sets",
  quality: "Quality Metrics",
  analytics: "Analytics",
  visualizations: "Visualizations",
  survival: "Survival Analysis",
  geospatial: "Geospatial",
  pathways: "Care Pathways",
  research: "Research",
  streaming: "Real-time",
  alerts: "Alerts",
  risks: "Risk Analysis",
  graph: "Knowledge Graph",
  models: "ML Models",
  cohorts: "Cohorts",
  builder: "Cohort Builder",
  compare: "Compare",
  notes: "Clinical Notes",
  editor: "Note Editor",
  cdisc: "CDISC",
  codelists: "Code Lists",
  cds: "Clinical Decision Support",
  test: "Test CDS",
  exports: "Data Exports",
  assistant: "AI Assistant",
  login: "Login",
  register: "Register",
  "forgot-password": "Forgot Password",
  facts: "Clinical Facts",
  timeline: "Timeline",
  summary: "Summary",
  jobs: "Jobs",
};

/**
 * Dynamic parameter labels - these are shown when we have dynamic routes
 * but no specific data to show
 */
const dynamicParamLabels: Record<string, string> = {
  patientId: "Patient",
  documentId: "Document",
  jobId: "Job",
  id: "Details",
  cCode: "Code List",
};

interface BreadcrumbItem {
  label: string;
  href: string;
  isCurrentPage: boolean;
  isTruncated?: boolean;
}

interface BreadcrumbProps {
  className?: string;
  /**
   * Custom labels for dynamic route parameters
   * e.g., { patientId: "John Smith", documentId: "Discharge Summary" }
   */
  dynamicLabels?: Record<string, string>;
  /**
   * Maximum character length before truncating a breadcrumb item
   * Default: 20
   */
  maxLength?: number;
  /**
   * Show home icon at the root
   * Default: true
   */
  showHomeIcon?: boolean;
  /**
   * Custom home label
   * Default: "Home"
   */
  homeLabel?: string;
  /**
   * Separator component between breadcrumb items
   */
  separator?: React.ReactNode;
}

/**
 * Truncate text if it exceeds maxLength
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 1) + "\u2026"; // ellipsis character
}

/**
 * Check if a segment is a dynamic parameter (starts with [ and ends with ])
 * or looks like an ID (alphanumeric with dashes)
 */
function isDynamicSegment(segment: string): boolean {
  // Check for Next.js dynamic route format
  if (segment.startsWith("[") && segment.endsWith("]")) return true;

  // Check for UUID-like patterns
  const uuidPattern = /^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
  if (uuidPattern.test(segment)) return true;

  // Check for common ID patterns (all numeric or alphanumeric with specific patterns)
  const idPatterns = [
    /^[A-Z]?\d{3,}$/i, // P001, D001, etc.
    /^[a-z]+-[a-z0-9]+$/i, // kebab-case IDs
  ];

  return idPatterns.some(pattern => pattern.test(segment));
}

/**
 * Extract parameter name from dynamic segment
 */
function extractParamName(segment: string): string {
  if (segment.startsWith("[") && segment.endsWith("]")) {
    return segment.slice(1, -1);
  }
  return segment;
}

/**
 * Dynamic breadcrumb navigation component
 * Auto-generates breadcrumbs from the current route
 */
export function Breadcrumb({
  className,
  dynamicLabels = {},
  maxLength = 20,
  showHomeIcon = true,
  homeLabel = "Home",
  separator,
}: BreadcrumbProps) {
  const pathname = usePathname();

  // Generate breadcrumb items from pathname
  const breadcrumbItems = React.useMemo((): BreadcrumbItem[] => {
    if (!pathname || pathname === "/") {
      return [];
    }

    const segments = pathname.split("/").filter(Boolean);
    const items: BreadcrumbItem[] = [];

    let currentPath = "";

    segments.forEach((segment, index) => {
      currentPath += `/${segment}`;
      const isCurrentPage = index === segments.length - 1;
      const previousSegment = segments[index - 1];

      let label: string;

      // Check if this is a dynamic segment
      if (isDynamicSegment(segment)) {
        // Try to get custom label from dynamicLabels
        const paramName = previousSegment
          ? `${previousSegment.slice(0, -1)}Id` // patients -> patientId
          : extractParamName(segment);

        if (dynamicLabels[segment]) {
          label = dynamicLabels[segment];
        } else if (dynamicLabels[paramName]) {
          label = dynamicLabels[paramName];
        } else {
          // Use the dynamic param label or default
          label = dynamicParamLabels[paramName] || segment;
        }
      } else {
        // Use route name mapping or capitalize the segment
        label = routeNames[segment] ||
          segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ");
      }

      const isTruncated = label.length > maxLength;
      const displayLabel = truncateText(label, maxLength);

      items.push({
        label: displayLabel,
        href: currentPath,
        isCurrentPage,
        isTruncated,
      });
    });

    return items;
  }, [pathname, dynamicLabels, maxLength]);

  // Don't render if on home page or no breadcrumbs
  if (breadcrumbItems.length === 0) {
    return null;
  }

  const defaultSeparator = (
    <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
  );

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center text-sm", className)}
    >
      <ol className="flex items-center gap-1.5">
        {/* Home link */}
        <li className="flex items-center gap-1.5">
          <Link
            href="/"
            className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
            aria-label={homeLabel}
          >
            {showHomeIcon ? (
              <Home className="h-4 w-4" />
            ) : (
              <span>{homeLabel}</span>
            )}
          </Link>
        </li>

        {/* Breadcrumb items */}
        {breadcrumbItems.map((item, index) => (
          <li key={item.href} className="flex items-center gap-1.5">
            {separator || defaultSeparator}
            {item.isCurrentPage ? (
              <span
                className="font-medium text-foreground truncate max-w-[200px]"
                aria-current="page"
                title={item.isTruncated ? item.label : undefined}
              >
                {item.label}
              </span>
            ) : (
              <Link
                href={item.href}
                className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[200px]"
                title={item.isTruncated ? item.label : undefined}
              >
                {item.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/**
 * Breadcrumb container with consistent styling
 */
interface BreadcrumbContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function BreadcrumbContainer({
  children,
  className,
}: BreadcrumbContainerProps) {
  return (
    <div
      className={cn(
        "flex items-center min-h-10 px-4 lg:px-6 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * Wrapper that combines BreadcrumbContainer and Breadcrumb
 * Provides a complete breadcrumb bar solution
 */
interface BreadcrumbBarProps extends BreadcrumbProps {
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
}

export function BreadcrumbBar({
  leftContent,
  rightContent,
  className,
  ...breadcrumbProps
}: BreadcrumbBarProps) {
  return (
    <BreadcrumbContainer className={className}>
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center gap-4">
          {leftContent}
          <Breadcrumb {...breadcrumbProps} />
        </div>
        {rightContent && <div>{rightContent}</div>}
      </div>
    </BreadcrumbContainer>
  );
}

export default Breadcrumb;
