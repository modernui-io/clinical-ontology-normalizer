"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowDown, ClipboardCheck } from "lucide-react";

interface ChecklistItem {
  id: string;
  label: string;
  checked: boolean;
}

const DEFAULT_CHECKLIST: ChecklistItem[] = [
  {
    id: "scenarios-executed",
    label: "All 3 scenarios executed successfully in last 24 hours",
    checked: false,
  },
  {
    id: "evidence-spot-checked",
    label: "Evidence bundles downloaded and spot-checked",
    checked: false,
  },
  {
    id: "no-simulation-banners",
    label: "No simulation banners visible on demo path (or explicitly acknowledged)",
    checked: false,
  },
  {
    id: "provenance-verified",
    label: "Provenance chain verified for at least 1 scenario end-to-end",
    checked: false,
  },
  {
    id: "reviewer-recorded",
    label: "Reviewer name and sign-off date recorded",
    checked: false,
  },
  {
    id: "env-matches-prod",
    label: "Demo environment matches production configuration (or deviations documented)",
    checked: false,
  },
];

function downloadJSON(filename: string, content: string) {
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

interface ReviewerChecklistProps {
  scenarioIds: string[];
}

export default function ReviewerChecklist({ scenarioIds }: ReviewerChecklistProps) {
  const [items, setItems] = useState<ChecklistItem[]>(DEFAULT_CHECKLIST);
  const [reviewerName, setReviewerName] = useState("");
  const [signoffDate, setSignoffDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const toggleItem = (id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, checked: !item.checked } : item
      )
    );
  };

  const exportSignoff = () => {
    const payload = {
      reviewer_name: reviewerName,
      signoff_date: signoffDate,
      exported_at_utc: new Date().toISOString(),
      scenario_ids: scenarioIds,
      checklist_items: items.map((item) => ({
        id: item.id,
        label: item.label,
        checked: item.checked,
      })),
    };
    const filename = `reviewer-signoff-${signoffDate}.json`;
    downloadJSON(filename, JSON.stringify(payload, null, 2));
  };

  const allChecked = items.every((item) => item.checked);

  return (
    <section className="rounded-xl border border-slate-200 p-5 bg-white">
      <div className="flex items-center gap-2 mb-4">
        <ClipboardCheck className="h-4 w-4 text-slate-700" />
        <h2 className="text-lg font-semibold text-slate-900">
          Reviewer Checklist
        </h2>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <label
            key={item.id}
            className="flex items-start gap-3 cursor-pointer group"
          >
            <Checkbox
              checked={item.checked}
              onCheckedChange={() => toggleItem(item.id)}
              className="mt-0.5"
            />
            <span
              className={`text-sm leading-snug ${
                item.checked
                  ? "text-slate-500 line-through"
                  : "text-slate-700"
              }`}
            >
              {item.label}
            </span>
          </label>
        ))}
      </div>

      <div className="mt-5 grid sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Reviewer name
          </label>
          <Input
            value={reviewerName}
            onChange={(e) => setReviewerName(e.target.value)}
            placeholder="Enter reviewer name"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Sign-off date
          </label>
          <Input
            type="date"
            value={signoffDate}
            onChange={(e) => setSignoffDate(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-xs text-slate-500">
          {items.filter((i) => i.checked).length}/{items.length} items checked
          {allChecked && reviewerName ? (
            <span className="ml-2 text-emerald-600 font-medium">
              Ready for sign-off
            </span>
          ) : null}
        </p>
        <Button
          variant="outline"
          onClick={exportSignoff}
          disabled={!reviewerName}
          className="inline-flex items-center gap-1.5"
        >
          <ArrowDown className="h-3.5 w-3.5" />
          Save Reviewer Signoff
        </Button>
      </div>
    </section>
  );
}
