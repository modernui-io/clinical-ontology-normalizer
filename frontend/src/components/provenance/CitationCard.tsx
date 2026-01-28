"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { BookOpen, Building2, ChevronDown, ChevronRight } from "lucide-react";
import type { GuidelineCitation, PolicyCitation } from "@/types/provenance";

const GRADE_COLORS: Record<string, string> = {
  "A": "bg-green-100 text-green-800 border-green-300",
  "B": "bg-blue-100 text-blue-800 border-blue-300",
  "C": "bg-yellow-100 text-yellow-800 border-yellow-300",
  "D": "bg-orange-100 text-orange-800 border-orange-300",
  "I": "bg-gray-100 text-gray-800 border-gray-300",
};

interface GuidelineCitationCardProps {
  citation: GuidelineCitation;
}

export function GuidelineCitationCard({ citation }: GuidelineCitationCardProps) {
  const [open, setOpen] = useState(false);
  const gradeColor = GRADE_COLORS[citation.evidence_grade?.charAt(0)?.toUpperCase()] || GRADE_COLORS["I"];
  const borderColor = citation.evidence_grade?.startsWith("A")
    ? "border-l-green-500"
    : citation.evidence_grade?.startsWith("B")
    ? "border-l-blue-500"
    : "border-l-yellow-500";

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className={`border-l-4 ${borderColor}`}>
        <CollapsibleTrigger asChild>
          <CardHeader className="py-2 px-3 cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <CardTitle className="text-sm font-medium flex-1 truncate">
                [Guideline {citation.guideline_number}] {citation.guideline}
              </CardTitle>
              <Badge variant="outline" className={`${gradeColor} text-xs`}>
                {citation.evidence_grade}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {citation.recommendation_level}
              </Badge>
              {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </div>
            <p className="text-xs text-muted-foreground ml-6 truncate">{citation.section_title}</p>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0 pb-3 px-3">
            <div className="ml-6 space-y-2">
              <p className="text-sm leading-relaxed">{citation.recommendation_text}</p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="outline" className="text-xs">
                  Relevance: {Math.round(citation.relevance_score * 100)}%
                </Badge>
                {citation.match_reasons?.map((reason, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {reason}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

interface PolicyCitationCardProps {
  citation: PolicyCitation;
}

export function PolicyCitationCard({ citation }: PolicyCitationCardProps) {
  return (
    <Card className="border-l-4 border-l-purple-500">
      <CardHeader className="py-2 px-3">
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <CardTitle className="text-sm font-medium flex-1 truncate">
            [Policy {citation.policy_number}] {citation.policy_name}
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {Math.round(citation.relevance_score * 100)}%
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground ml-6">{citation.section_title}</p>
      </CardHeader>
    </Card>
  );
}
