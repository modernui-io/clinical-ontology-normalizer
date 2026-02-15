"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Stethoscope,
  DollarSign,
  Settings,
  Brain,
  Network,
  HelpCircle,
  BarChart3,
  CreditCard,
  FileText,
  Shield,
  Activity,
  Server,
  ClipboardList,
} from "lucide-react";

// ---------------------------------------------------------------------------
// P3-002: Persona-based navigation for pilot usability
// ---------------------------------------------------------------------------

interface PersonaLink {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface Persona {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  activeColor: string;
  links: PersonaLink[];
}

const personas: Persona[] = [
  {
    id: "clinical",
    label: "Clinical",
    description: "NLP, knowledge graphs, and Q&A tools",
    icon: Stethoscope,
    color: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
    activeColor: "border-blue-400 bg-blue-100 ring-2 ring-blue-400/30 dark:border-blue-600 dark:bg-blue-900 dark:ring-blue-500/30",
    links: [
      { title: "NLP Workbench", href: "/nlp", icon: Brain },
      { title: "Clinical Dashboard", href: "/clinical", icon: Stethoscope },
      { title: "Knowledge Graph", href: "/analytics/graph", icon: Network },
      { title: "AI Assistant", href: "/assistant", icon: HelpCircle },
    ],
  },
  {
    id: "rcm",
    label: "Revenue Cycle",
    description: "Billing, coding, and claims workflows",
    icon: DollarSign,
    color: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
    activeColor: "border-emerald-400 bg-emerald-100 ring-2 ring-emerald-400/30 dark:border-emerald-600 dark:bg-emerald-900 dark:ring-emerald-500/30",
    links: [
      { title: "Billing", href: "/billing", icon: CreditCard },
      { title: "AI Auto-Coding", href: "/ai-coding", icon: FileText },
      { title: "Claims", href: "/billing", icon: DollarSign },
    ],
  },
  {
    id: "it",
    label: "IT Admin",
    description: "System health, audit, and administration",
    icon: Settings,
    color: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
    activeColor: "border-slate-400 bg-slate-100 ring-2 ring-slate-400/30 dark:border-slate-600 dark:bg-slate-800 dark:ring-slate-500/30",
    links: [
      { title: "Health", href: "/admin/dashboard", icon: Activity },
      { title: "Audit Log", href: "/audit", icon: ClipboardList },
      { title: "Admin", href: "/admin/users", icon: Server },
      { title: "Analytics", href: "/analytics/visualizations", icon: BarChart3 },
    ],
  },
];

interface PersonaNavigatorProps {
  className?: string;
  compact?: boolean;
}

export function PersonaNavigator({ className, compact = false }: PersonaNavigatorProps) {
  const pathname = usePathname();
  const [activePersona, setActivePersona] = useState<string | null>(() => {
    // Auto-detect persona from current path
    for (const persona of personas) {
      if (persona.links.some((link) => pathname.startsWith(link.href))) {
        return persona.id;
      }
    }
    return null;
  });

  if (compact) {
    return (
      <div className={cn("flex flex-col gap-1", className)}>
        {personas.map((persona) => {
          const Icon = persona.icon;
          const isActive = activePersona === persona.id;
          return (
            <div key={persona.id}>
              <button
                onClick={() => setActivePersona(isActive ? null : persona.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                  isActive
                    ? persona.activeColor
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span>{persona.label}</span>
              </button>
              {isActive && (
                <div className="ml-4 mt-1 flex flex-col gap-0.5 border-l border-border pl-2">
                  {persona.links.map((link) => {
                    const LinkIcon = link.icon;
                    const linkActive = pathname.startsWith(link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors",
                          linkActive
                            ? "bg-accent font-medium text-accent-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <LinkIcon className="h-3 w-3 shrink-0" />
                        {link.title}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-3", className)}>
      {personas.map((persona) => {
        const Icon = persona.icon;
        const isActive = activePersona === persona.id;
        return (
          <Card
            key={persona.id}
            className={cn(
              "cursor-pointer transition-all",
              isActive ? persona.activeColor : persona.color
            )}
            onClick={() => setActivePersona(isActive ? null : persona.id)}
          >
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Icon className="h-4 w-4" />
                {persona.label}
              </CardTitle>
              <p className="text-xs opacity-70">{persona.description}</p>
            </CardHeader>
            {isActive && (
              <CardContent className="pt-0">
                <div className="flex flex-col gap-1">
                  {persona.links.map((link) => {
                    const LinkIcon = link.icon;
                    const linkActive = pathname.startsWith(link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                          linkActive
                            ? "bg-background/80 text-foreground"
                            : "hover:bg-background/50"
                        )}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <LinkIcon className="h-3.5 w-3.5 shrink-0" />
                        {link.title}
                      </Link>
                    );
                  })}
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}
