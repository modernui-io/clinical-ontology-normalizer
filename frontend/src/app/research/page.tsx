"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  FlaskConical,
  Play,
  CheckCircle,
  Clock,
  AlertTriangle,
  BarChart3,
  Database,
  Network,
} from "lucide-react";
import { useExperiments } from "@/hooks/api/useResearch";

export default function ResearchDashboardPage() {
  const { data: experiments, isLoading } = useExperiments();

  const stats = {
    total: experiments?.total ?? 0,
    running: experiments?.experiments.filter((e) => e.status === "running").length ?? 0,
    completed: experiments?.experiments.filter((e) => e.status === "completed").length ?? 0,
    draft: experiments?.experiments.filter((e) => e.status === "draft").length ?? 0,
  };

  const recentExperiments = experiments?.experiments.slice(0, 5) ?? [];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <FlaskConical className="h-6 w-6" />
                Research Lab
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                NeurIPS 2026 - Epistemic Knowledge Graphs
              </p>
            </div>
            <Link href="/research/experiments">
              <Button>New Experiment</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <FlaskConical className="h-8 w-8 text-blue-500" />
                  <div>
                    <p className="text-2xl font-bold">{stats.total}</p>
                    <p className="text-sm text-muted-foreground">Total Experiments</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <Play className="h-8 w-8 text-green-500" />
                  <div>
                    <p className="text-2xl font-bold">{stats.running}</p>
                    <p className="text-sm text-muted-foreground">Running</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-8 w-8 text-emerald-500" />
                  <div>
                    <p className="text-2xl font-bold">{stats.completed}</p>
                    <p className="text-sm text-muted-foreground">Completed</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <Clock className="h-8 w-8 text-amber-500" />
                  <div>
                    <p className="text-2xl font-bold">{stats.draft}</p>
                    <p className="text-sm text-muted-foreground">Drafts</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link href="/research/ingest">
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Database className="h-5 w-5" />
                    Data Ingestion
                  </CardTitle>
                  <CardDescription>Import MIMIC-IV data with experiment tagging</CardDescription>
                </CardHeader>
              </Card>
            </Link>
            <Link href="/research/pipeline">
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <BarChart3 className="h-5 w-5" />
                    Pipeline Monitor
                  </CardTitle>
                  <CardDescription>Watch NLP, OMOP, Facts, KG in real-time</CardDescription>
                </CardHeader>
              </Card>
            </Link>
            <Link href="/research/compare">
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Network className="h-5 w-5" />
                    Compare Runs
                  </CardTitle>
                  <CardDescription>Side-by-side experiment comparison</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          </div>

          {/* Recent Experiments */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Experiments</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-muted-foreground">Loading experiments...</p>
              ) : recentExperiments.length === 0 ? (
                <div className="text-center py-8">
                  <FlaskConical className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-muted-foreground">No experiments yet</p>
                  <Link href="/research/experiments">
                    <Button variant="outline" className="mt-3">
                      Create First Experiment
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="space-y-2">
                  {recentExperiments.map((exp) => (
                    <Link
                      key={exp.id}
                      href={`/research/experiments?id=${exp.id}`}
                      className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div>
                        <p className="font-medium">{exp.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {exp.run_count} run{exp.run_count !== 1 ? "s" : ""} &middot;{" "}
                          {new Date(exp.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          exp.status === "completed"
                            ? "bg-emerald-100 text-emerald-700"
                            : exp.status === "running"
                              ? "bg-blue-100 text-blue-700"
                              : exp.status === "failed"
                                ? "bg-red-100 text-red-700"
                                : "bg-zinc-100 text-zinc-700"
                        }`}
                      >
                        {exp.status === "running" && <Play className="h-3 w-3" />}
                        {exp.status === "completed" && <CheckCircle className="h-3 w-3" />}
                        {exp.status === "failed" && <AlertTriangle className="h-3 w-3" />}
                        {exp.status}
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
