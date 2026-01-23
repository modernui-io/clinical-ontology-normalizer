"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  Search,
  Beaker,
  AlertTriangle,
} from "lucide-react";

interface LabTest {
  name: string;
  loinc: string;
  unit: string;
  ranges: {
    population: string;
    low: number | null;
    high: number | null;
    critical_low: number | null;
    critical_high: number | null;
  }[];
  category: string;
  specimen: string;
  notes?: string;
}

const LAB_PANELS: Record<string, LabTest[]> = {
  "Basic Metabolic Panel (BMP)": [
    { name: "Glucose", loinc: "2345-7", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 70, high: 100, critical_low: 40, critical_high: 500 }] },
    { name: "BUN", loinc: "3094-0", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 7, high: 20, critical_low: null, critical_high: 100 }] },
    { name: "Creatinine", loinc: "2160-0", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [
        { population: "Adult Male", low: 0.7, high: 1.3, critical_low: null, critical_high: 10 },
        { population: "Adult Female", low: 0.6, high: 1.1, critical_low: null, critical_high: 10 },
      ] },
    { name: "Sodium", loinc: "2951-2", unit: "mEq/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 136, high: 145, critical_low: 120, critical_high: 160 }] },
    { name: "Potassium", loinc: "2823-3", unit: "mEq/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 3.5, high: 5.0, critical_low: 2.5, critical_high: 6.5 }] },
    { name: "Chloride", loinc: "2075-0", unit: "mEq/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 98, high: 106, critical_low: 80, critical_high: 120 }] },
    { name: "CO2 (Bicarbonate)", loinc: "2028-9", unit: "mEq/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 23, high: 29, critical_low: 10, critical_high: 40 }] },
    { name: "Calcium", loinc: "17861-6", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 8.5, high: 10.5, critical_low: 6.0, critical_high: 14.0 }] },
  ],
  "Complete Blood Count (CBC)": [
    { name: "WBC", loinc: "6690-2", unit: "x10^3/uL", category: "Hematology", specimen: "Whole Blood",
      ranges: [{ population: "Adult", low: 4.5, high: 11.0, critical_low: 2.0, critical_high: 30.0 }] },
    { name: "RBC", loinc: "789-8", unit: "x10^6/uL", category: "Hematology", specimen: "Whole Blood",
      ranges: [
        { population: "Adult Male", low: 4.5, high: 5.9, critical_low: null, critical_high: null },
        { population: "Adult Female", low: 4.0, high: 5.2, critical_low: null, critical_high: null },
      ] },
    { name: "Hemoglobin", loinc: "718-7", unit: "g/dL", category: "Hematology", specimen: "Whole Blood",
      ranges: [
        { population: "Adult Male", low: 13.5, high: 17.5, critical_low: 7.0, critical_high: 20.0 },
        { population: "Adult Female", low: 12.0, high: 16.0, critical_low: 7.0, critical_high: 20.0 },
      ] },
    { name: "Hematocrit", loinc: "4544-3", unit: "%", category: "Hematology", specimen: "Whole Blood",
      ranges: [
        { population: "Adult Male", low: 38.3, high: 48.6, critical_low: 20, critical_high: 60 },
        { population: "Adult Female", low: 35.5, high: 44.9, critical_low: 20, critical_high: 60 },
      ] },
    { name: "Platelets", loinc: "777-3", unit: "x10^3/uL", category: "Hematology", specimen: "Whole Blood",
      ranges: [{ population: "Adult", low: 150, high: 400, critical_low: 50, critical_high: 1000 }] },
    { name: "MCV", loinc: "787-2", unit: "fL", category: "Hematology", specimen: "Whole Blood",
      ranges: [{ population: "Adult", low: 80, high: 100, critical_low: null, critical_high: null }] },
  ],
  "Comprehensive Metabolic Panel (CMP)": [
    { name: "Albumin", loinc: "1751-7", unit: "g/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 3.5, high: 5.5, critical_low: 1.5, critical_high: null }] },
    { name: "Total Protein", loinc: "2885-2", unit: "g/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 6.0, high: 8.3, critical_low: null, critical_high: null }] },
    { name: "ALP", loinc: "6768-6", unit: "U/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 44, high: 147, critical_low: null, critical_high: null }] },
    { name: "ALT", loinc: "1742-6", unit: "U/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 7, high: 56, critical_low: null, critical_high: null }] },
    { name: "AST", loinc: "1920-8", unit: "U/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 10, high: 40, critical_low: null, critical_high: null }] },
    { name: "Total Bilirubin", loinc: "1975-2", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 0.1, high: 1.2, critical_low: null, critical_high: 12.0 }] },
  ],
  "Lipid Panel": [
    { name: "Total Cholesterol", loinc: "2093-3", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: null, high: 200, critical_low: null, critical_high: null }],
      notes: "Desirable: <200; Borderline: 200-239; High: >=240" },
    { name: "LDL Cholesterol", loinc: "2089-1", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: null, high: 100, critical_low: null, critical_high: null }],
      notes: "Optimal: <100; Near optimal: 100-129; Borderline: 130-159; High: >=160" },
    { name: "HDL Cholesterol", loinc: "2085-9", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [
        { population: "Adult Male", low: 40, high: null, critical_low: null, critical_high: null },
        { population: "Adult Female", low: 50, high: null, critical_low: null, critical_high: null },
      ] },
    { name: "Triglycerides", loinc: "2571-8", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: null, high: 150, critical_low: null, critical_high: null }],
      notes: "Normal: <150; Borderline: 150-199; High: 200-499; Very High: >=500" },
  ],
  "Thyroid Panel": [
    { name: "TSH", loinc: "3016-3", unit: "mIU/L", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 0.27, high: 4.2, critical_low: null, critical_high: null }] },
    { name: "Free T4", loinc: "3024-7", unit: "ng/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 0.9, high: 1.7, critical_low: null, critical_high: null }] },
    { name: "Free T3", loinc: "3051-0", unit: "pg/mL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 2.0, high: 4.4, critical_low: null, critical_high: null }] },
  ],
  "Coagulation": [
    { name: "PT", loinc: "5902-2", unit: "seconds", category: "Coagulation", specimen: "Plasma",
      ranges: [{ population: "Adult", low: 11.0, high: 13.5, critical_low: null, critical_high: 30 }] },
    { name: "INR", loinc: "6301-6", unit: "ratio", category: "Coagulation", specimen: "Plasma",
      ranges: [{ population: "Adult (no therapy)", low: 0.8, high: 1.1, critical_low: null, critical_high: 5.0 }],
      notes: "Therapeutic range for warfarin: 2.0-3.0 (general); 2.5-3.5 (mechanical valve)" },
    { name: "aPTT", loinc: "3173-2", unit: "seconds", category: "Coagulation", specimen: "Plasma",
      ranges: [{ population: "Adult", low: 25, high: 35, critical_low: null, critical_high: 100 }] },
  ],
  "Diabetes Monitoring": [
    { name: "HbA1c", loinc: "4548-4", unit: "%", category: "Chemistry", specimen: "Whole Blood",
      ranges: [{ population: "Non-diabetic", low: null, high: 5.7, critical_low: null, critical_high: null }],
      notes: "Normal: <5.7%; Prediabetes: 5.7-6.4%; Diabetes: >=6.5%; Target for diabetes: <7%" },
    { name: "Fasting Glucose", loinc: "1558-6", unit: "mg/dL", category: "Chemistry", specimen: "Serum",
      ranges: [{ population: "Adult", low: 70, high: 100, critical_low: 40, critical_high: 500 }],
      notes: "Normal: <100; Prediabetes: 100-125; Diabetes: >=126" },
  ],
};

export default function LabReferenceRangePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPanel, setSelectedPanel] = useState<string | null>(null);

  const panelNames = Object.keys(LAB_PANELS);

  const filteredPanels = searchQuery.trim()
    ? panelNames.filter((panel) => {
        const tests = LAB_PANELS[panel];
        return (
          panel.toLowerCase().includes(searchQuery.toLowerCase()) ||
          tests.some(
            (t) =>
              t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              t.loinc.includes(searchQuery)
          )
        );
      })
    : panelNames;

  const getFilteredTests = (panel: string): LabTest[] => {
    if (!searchQuery.trim()) return LAB_PANELS[panel];
    return LAB_PANELS[panel].filter(
      (t) =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.loinc.includes(searchQuery)
    );
  };

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Lab Reference Ranges</h1>
          <p className="text-muted-foreground">
            Standard laboratory test reference ranges with LOINC codes
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by test name, LOINC code, or panel..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>

      {/* Panel Cards */}
      <div className="space-y-6">
        {filteredPanels.map((panelName) => {
          const tests = getFilteredTests(panelName);
          if (tests.length === 0) return null;

          return (
            <Card key={panelName}>
              <CardHeader
                className="pb-3 cursor-pointer"
                onClick={() =>
                  setSelectedPanel(selectedPanel === panelName ? null : panelName)
                }
              >
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Beaker className="h-5 w-5" />
                    {panelName}
                  </CardTitle>
                  <Badge variant="outline">{tests.length} tests</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4 font-medium">Test</th>
                        <th className="text-left py-2 pr-4 font-medium">LOINC</th>
                        <th className="text-left py-2 pr-4 font-medium">Population</th>
                        <th className="text-center py-2 pr-4 font-medium">Low</th>
                        <th className="text-center py-2 pr-4 font-medium">High</th>
                        <th className="text-left py-2 pr-4 font-medium">Unit</th>
                        <th className="text-center py-2 font-medium">Critical</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tests.map((test) =>
                        test.ranges.map((range, idx) => (
                          <tr key={`${test.loinc}-${idx}`} className="border-b last:border-0">
                            {idx === 0 && (
                              <>
                                <td className="py-2 pr-4 font-medium" rowSpan={test.ranges.length}>
                                  {test.name}
                                  {test.notes && (
                                    <p className="text-xs text-muted-foreground font-normal mt-0.5">
                                      {test.notes}
                                    </p>
                                  )}
                                </td>
                                <td className="py-2 pr-4" rowSpan={test.ranges.length}>
                                  <code className="text-xs bg-muted px-1 py-0.5 rounded">
                                    {test.loinc}
                                  </code>
                                </td>
                              </>
                            )}
                            <td className="py-2 pr-4 text-muted-foreground text-xs">
                              {range.population}
                            </td>
                            <td className="py-2 pr-4 text-center font-mono">
                              {range.low !== null ? range.low : "-"}
                            </td>
                            <td className="py-2 pr-4 text-center font-mono">
                              {range.high !== null ? range.high : "-"}
                            </td>
                            {idx === 0 && (
                              <td className="py-2 pr-4 text-muted-foreground" rowSpan={test.ranges.length}>
                                {test.unit}
                              </td>
                            )}
                            <td className="py-2 text-center">
                              {(range.critical_low !== null || range.critical_high !== null) && (
                                <span className="text-xs text-red-600 flex items-center justify-center gap-0.5">
                                  <AlertTriangle className="h-3 w-3" />
                                  {range.critical_low !== null ? `<${range.critical_low}` : ""}
                                  {range.critical_low !== null && range.critical_high !== null ? " / " : ""}
                                  {range.critical_high !== null ? `>${range.critical_high}` : ""}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
