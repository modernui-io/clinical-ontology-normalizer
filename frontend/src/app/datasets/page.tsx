"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMimicMetrics } from "@/hooks/api/useMimic";
import { useMtsamplesMetrics } from "@/hooks/api/useMtsamples";
import { useSyntheaMetrics } from "@/hooks/api/useSynthea";

function StatBadge({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="text-center">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export default function DatasetsHubPage() {
  const { data: mimicMetrics } = useMimicMetrics();
  const { data: mtsamplesMetrics } = useMtsamplesMetrics();
  const { data: syntheaMetrics } = useSyntheaMetrics();

  const datasets = [
    {
      name: "MIMIC-IV-Note",
      description: "Critical care discharge summaries and radiology reports from Beth Israel Deaconess Medical Center. 331K+ real clinical notes.",
      href: "/mimic",
      validationHref: "/mimic/validation",
      badge: "PhysioNet",
      badgeVariant: "secondary" as const,
      stats: mimicMetrics
        ? {
            docs: mimicMetrics.total_documents,
            mentions: mimicMetrics.total_mentions,
            facts: mimicMetrics.total_facts,
            coverage: `${mimicMetrics.concept_coverage_percent}%`,
          }
        : null,
    },
    {
      name: "MTSamples",
      description: "5K medical transcriptions across 40+ specialties including surgery, cardiology, orthopedics, radiology, and more.",
      href: "/datasets/mtsamples",
      validationHref: "/datasets/mtsamples/validation",
      badge: "Free",
      badgeVariant: "default" as const,
      stats: mtsamplesMetrics
        ? {
            docs: mtsamplesMetrics.total_documents,
            mentions: mtsamplesMetrics.total_mentions,
            facts: mtsamplesMetrics.total_facts,
            coverage: `${mtsamplesMetrics.concept_coverage_percent}%`,
          }
        : null,
    },
    {
      name: "Synthea",
      description: "Synthetic patient records generated from clinical models. Rich structured data (encounters, conditions, medications, labs) composed into clinical notes.",
      href: "/datasets/synthea",
      validationHref: "/datasets/synthea/validation",
      badge: "Free",
      badgeVariant: "default" as const,
      stats: syntheaMetrics
        ? {
            docs: syntheaMetrics.total_documents,
            mentions: syntheaMetrics.total_mentions,
            facts: syntheaMetrics.total_facts,
            coverage: `${syntheaMetrics.concept_coverage_percent}%`,
          }
        : null,
    },
  ];

  const totalDocs =
    (mimicMetrics?.total_documents ?? 0) +
    (mtsamplesMetrics?.total_documents ?? 0) +
    (syntheaMetrics?.total_documents ?? 0);
  const totalMentions =
    (mimicMetrics?.total_mentions ?? 0) +
    (mtsamplesMetrics?.total_mentions ?? 0) +
    (syntheaMetrics?.total_mentions ?? 0);
  const totalFacts =
    (mimicMetrics?.total_facts ?? 0) +
    (mtsamplesMetrics?.total_facts ?? 0) +
    (syntheaMetrics?.total_facts ?? 0);

  return (
    <div className="container mx-auto p-6 max-w-6xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Clinical Datasets</h1>
        <p className="text-muted-foreground mt-1">
          Import and validate clinical data from multiple sources. Each dataset flows through the NLP pipeline for concept extraction, OMOP mapping, and fact building.
        </p>
      </div>

      {/* Aggregate Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{totalDocs.toLocaleString()}</div>
            <div className="text-sm text-muted-foreground">Total Documents</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{totalMentions.toLocaleString()}</div>
            <div className="text-sm text-muted-foreground">Total Mentions</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{totalFacts.toLocaleString()}</div>
            <div className="text-sm text-muted-foreground">Total Facts</div>
          </CardContent>
        </Card>
      </div>

      {/* Dataset Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {datasets.map((ds) => (
          <Card key={ds.name} className="flex flex-col">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{ds.name}</CardTitle>
                <Badge variant={ds.badgeVariant}>{ds.badge}</Badge>
              </div>
              <CardDescription className="text-sm">{ds.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col justify-between space-y-4">
              {ds.stats && ds.stats.docs > 0 ? (
                <div className="grid grid-cols-4 gap-2">
                  <StatBadge value={ds.stats.docs.toLocaleString()} label="Docs" />
                  <StatBadge value={ds.stats.mentions.toLocaleString()} label="Mentions" />
                  <StatBadge value={ds.stats.facts.toLocaleString()} label="Facts" />
                  <StatBadge value={ds.stats.coverage} label="Coverage" />
                </div>
              ) : (
                <div className="text-center text-muted-foreground text-sm py-4">
                  No data imported yet
                </div>
              )}
              <div className="flex gap-2">
                <Button asChild className="flex-1">
                  <Link href={ds.href}>Import</Link>
                </Button>
                {ds.stats && ds.stats.docs > 0 && (
                  <Button asChild variant="outline" className="flex-1">
                    <Link href={ds.validationHref}>Validate</Link>
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
