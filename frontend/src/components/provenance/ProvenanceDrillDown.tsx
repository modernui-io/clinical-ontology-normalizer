"use client";

import { useState, useEffect } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Layers,
  Search,
  BookOpen,
  Brain,
  FileText,
  ChevronRight,
} from "lucide-react";
import type {
  ReasoningStep,
  GuidelineCitation,
  PolicyCitation,
  EntityProvenance,
  FactLineage,
} from "@/types/provenance";

interface ProvenanceDrillDownProps {
  queryId: string | null;
  reasoningSteps: ReasoningStep[];
  guidelineCitations: GuidelineCitation[];
  policyCitations: PolicyCitation[];
  entityProvenance: EntityProvenance[];
  patientId?: string | null;
}

function Breadcrumb({ path, onNavigate }: { path: string[]; onNavigate: (idx: number) => void }) {
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
      {path.map((item, idx) => (
        <span key={idx} className="flex items-center gap-1">
          {idx > 0 && <ChevronRight className="h-3 w-3" />}
          <button
            onClick={() => onNavigate(idx)}
            className={`hover:text-foreground transition-colors ${
              idx === path.length - 1 ? "text-foreground font-medium" : ""
            }`}
          >
            {item}
          </button>
        </span>
      ))}
    </div>
  );
}

function EntityProvenanceItem({ entity }: { entity: EntityProvenance }) {
  return (
    <div className="rounded-md border p-2 text-xs space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-medium">{entity.text}</span>
        <Badge variant="outline" className="text-xs">
          {entity.entity_type}
        </Badge>
      </div>
      <div className="flex items-center gap-2 text-muted-foreground">
        <span>Confidence: {Math.round(entity.confidence * 100)}%</span>
        {entity.extraction_method && (
          <>
            <span>|</span>
            <span>{entity.extraction_method}</span>
          </>
        )}
      </div>
      {entity.extracted_text && (
        <div className="bg-muted/50 rounded p-1.5 mt-1">
          <span className="text-muted-foreground">Source: </span>
          <span className="italic">{entity.extracted_text}</span>
        </div>
      )}
    </div>
  );
}

export function ProvenanceDrillDown({
  queryId,
  reasoningSteps,
  guidelineCitations,
  policyCitations,
  entityProvenance,
}: ProvenanceDrillDownProps) {
  const [breadcrumb, setBreadcrumb] = useState<string[]>(["Answer"]);

  const handleNavigate = (idx: number) => {
    setBreadcrumb((prev) => prev.slice(0, idx + 1));
  };

  const sortedSteps = [...reasoningSteps].sort((a, b) => a.step - b.step);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Layers className="h-3.5 w-3.5" />
          Provenance
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Provenance Drill-Down
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="h-[60vh]">
          <div className="pr-4 space-y-4">
            <Breadcrumb path={breadcrumb} onNavigate={handleNavigate} />

            {queryId && (
              <div className="text-xs text-muted-foreground">
                Query ID: <code className="font-mono">{queryId}</code>
              </div>
            )}

            <Accordion type="multiple" className="w-full">
              {/* Reasoning Steps */}
              <AccordionItem value="reasoning">
                <AccordionTrigger className="text-sm">
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-purple-500" />
                    Reasoning Steps ({sortedSteps.length})
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-2">
                    {sortedSteps.map((step) => (
                      <div
                        key={step.step}
                        className="rounded-md border p-2 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium capitalize">
                            Step {step.step}: {step.type.replace(/_/g, " ")}
                          </span>
                          <div className="flex gap-1">
                            <Badge variant="outline" className="text-xs">
                              {step.duration_ms.toFixed(0)}ms
                            </Badge>
                            {step.confidence_contribution != null &&
                              step.confidence_contribution > 0 && (
                                <Badge
                                  variant="secondary"
                                  className="text-xs text-green-600"
                                >
                                  +{Math.round(step.confidence_contribution * 100)}%
                                </Badge>
                              )}
                          </div>
                        </div>
                        <p className="text-muted-foreground">{step.summary}</p>
                        {step.details && Object.keys(step.details).length > 0 && (
                          <Accordion type="single" collapsible className="w-full">
                            <AccordionItem value="details" className="border-0">
                              <AccordionTrigger className="py-1 text-xs text-muted-foreground">
                                Details
                              </AccordionTrigger>
                              <AccordionContent>
                                <pre className="text-xs bg-muted/50 rounded p-2 overflow-x-auto">
                                  {JSON.stringify(step.details, null, 2)}
                                </pre>
                              </AccordionContent>
                            </AccordionItem>
                          </Accordion>
                        )}
                      </div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Guideline Citations */}
              {guidelineCitations.length > 0 && (
                <AccordionItem value="guidelines">
                  <AccordionTrigger className="text-sm">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-green-500" />
                      Guideline Citations ({guidelineCitations.length})
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {guidelineCitations.map((citation, idx) => (
                        <div
                          key={idx}
                          className="rounded-md border p-2 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">
                              [Guideline {citation.guideline_number}]{" "}
                              {citation.guideline}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {citation.evidence_grade}
                            </Badge>
                          </div>
                          <p className="text-muted-foreground">
                            {citation.section_title}
                          </p>
                          <p>{citation.recommendation_text}</p>
                          <div className="flex gap-1 flex-wrap">
                            <Badge variant="secondary" className="text-xs">
                              {citation.recommendation_level}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              Relevance:{" "}
                              {Math.round(citation.relevance_score * 100)}%
                            </Badge>
                            {citation.match_reasons?.map((reason, i) => (
                              <Badge
                                key={i}
                                variant="secondary"
                                className="text-xs"
                              >
                                {reason}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}

              {/* Policy Citations */}
              {policyCitations.length > 0 && (
                <AccordionItem value="policies">
                  <AccordionTrigger className="text-sm">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-indigo-500" />
                      Policy Citations ({policyCitations.length})
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {policyCitations.map((citation, idx) => (
                        <div
                          key={idx}
                          className="rounded-md border p-2 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">
                              [Policy {citation.policy_number}]{" "}
                              {citation.policy_name}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {Math.round(citation.relevance_score * 100)}%
                            </Badge>
                          </div>
                          <p className="text-muted-foreground">
                            {citation.section_title}
                          </p>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}

              {/* Entity Provenance */}
              {entityProvenance.length > 0 && (
                <AccordionItem value="entities">
                  <AccordionTrigger className="text-sm">
                    <div className="flex items-center gap-2">
                      <Search className="h-4 w-4 text-blue-500" />
                      Entity Provenance ({entityProvenance.length})
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {entityProvenance.map((entity, idx) => (
                        <EntityProvenanceItem key={idx} entity={entity} />
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )}
            </Accordion>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
