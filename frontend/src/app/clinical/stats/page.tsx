"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  RefreshCw,
  Database,
  BookOpen,
  Pill,
  Activity,
  Stethoscope,
  Target,
} from "lucide-react";

interface ServiceStats {
  name: string;
  icon: typeof Database;
  endpoint: string;
  data: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
}

export default function TerminologyStatsPage() {
  const [services, setServices] = useState<ServiceStats[]>([
    { name: "ICD-10-CM", icon: BookOpen, endpoint: "/api/icd10-suggestions/stats", data: null, loading: false, error: null },
    { name: "CPT Codes", icon: Stethoscope, endpoint: "/api/cpt-suggestions/stats", data: null, loading: false, error: null },
    { name: "Drug Safety", icon: Pill, endpoint: "/api/drug-safety/stats", data: null, loading: false, error: null },
    { name: "HCC Analysis", icon: Target, endpoint: "/api/hcc-analysis/stats", data: null, loading: false, error: null },
    { name: "Differential Dx", icon: Activity, endpoint: "/api/differential-diagnosis/stats", data: null, loading: false, error: null },
  ]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchStats = async () => {
    setIsRefreshing(true);
    const updated = await Promise.all(
      services.map(async (svc) => {
        try {
          const res = await fetch(svc.endpoint);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          return { ...svc, data, loading: false, error: null };
        } catch (err: unknown) {
          return {
            ...svc,
            data: null,
            loading: false,
            error: err instanceof Error ? err.message : "Failed",
          };
        }
      })
    );
    setServices(updated);
    setIsRefreshing(false);
  };

  useEffect(() => {
    fetchStats();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const renderValue = (value: unknown): string => {
    if (typeof value === "number") return value.toLocaleString();
    if (typeof value === "string") return value;
    if (typeof value === "object" && value !== null) {
      return Object.keys(value).length + " entries";
    }
    return String(value);
  };

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link href="/clinical">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Terminology Statistics</h1>
            <p className="text-muted-foreground">
              Overview of loaded terminology databases and service metrics
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStats}
          disabled={isRefreshing}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {services.map((svc) => {
          const Icon = svc.icon;
          return (
            <Card key={svc.name}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{svc.name}</CardTitle>
                    {svc.error && (
                      <Badge variant="destructive" className="text-xs mt-1">
                        Error
                      </Badge>
                    )}
                    {svc.data && !svc.error && (
                      <Badge variant="default" className="text-xs mt-1 bg-green-600">
                        Online
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {svc.error ? (
                  <p className="text-sm text-red-500">{svc.error}</p>
                ) : svc.data ? (
                  <div className="space-y-2">
                    {Object.entries(svc.data).map(([key, value]) => {
                      if (typeof value === "object" && value !== null && !Array.isArray(value)) {
                        return (
                          <div key={key}>
                            <p className="text-xs font-medium text-muted-foreground mb-1">
                              {key.replace(/_/g, " ")}
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {Object.entries(value as Record<string, unknown>)
                                .slice(0, 6)
                                .map(([k, v]) => (
                                  <Badge key={k} variant="outline" className="text-xs">
                                    {k}: {renderValue(v)}
                                  </Badge>
                                ))}
                              {Object.keys(value as Record<string, unknown>).length > 6 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{Object.keys(value as Record<string, unknown>).length - 6} more
                                </Badge>
                              )}
                            </div>
                          </div>
                        );
                      }
                      return (
                        <div key={key} className="flex justify-between items-center">
                          <span className="text-sm text-muted-foreground">
                            {key.replace(/_/g, " ")}
                          </span>
                          <span className="font-mono font-bold text-sm">
                            {renderValue(value)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex items-center justify-center py-4">
                    <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
