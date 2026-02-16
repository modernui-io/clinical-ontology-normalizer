import { promises as fs } from "node:fs";
import path from "node:path";

export interface BacklogTask {
  id: string;
  priority: string;
  title: string;
  owner: string;
  anchors: string[];
  exit: string;
  done: boolean;
  isSubtask: boolean;
  rawLine: string;
}

export interface EvidenceArtifact {
  path: string;
  status: "present" | "missing" | "unknown";
  lastUpdatedAt: string | null;
  relatedTaskIds: string[];
}

export interface BacklogSummary {
  generatedAt: string;
  sourceFile: string;
  sourceUpdatedAt: string | null;
  counts: {
    openTopLevelByPriority: Record<string, number>;
    openAll: Record<string, number>;
    doneAll: Record<string, number>;
    totalTopLevel: Record<string, number>;
    totalAll: Record<string, number>;
  };
  openTopLevel: BacklogTask[];
  openSubtasks: BacklogTask[];
  evidenceArtifacts: EvidenceArtifact[];
}

type CandidatePath = string;

const BACKLOG_FILE: CandidatePath = "tasks/09_master_change_backlog_p0_p4.md";

const TASK_LINE_RE = /^- \[([ xX])\]\s*(P\d{1,3}-\d{3}(?:-[A-Z])?)\s*(.*)$/;
const OWNER_RE = /^\s*Owner:\s*(.+?)\s*$/;
const ANCHOR_RE = /^\s*Anchor:\s*(.+?)\s*$/;
const EXIT_RE = /^\s*Exit:\s*(.+?)\s*$/;
const CHECKBOX_OPEN = " ";

const P0_EVIDENCE_HINTS: Record<string, string[]> = {
  "P0-019": [
    "docs/operations/openehr_reconciliation_rollback.md",
    "docs/operations/p0_019_evidence_capture_packet.md",
  ],
  "P0-025": [
    "docs/operations/incident_escalation_matrix.md",
    "docs/operations/incident_response_run_log.md",
  ],
  "P0-026": [
    "docs/operations/backup_restore_drill.md",
    "docs/evidence/backup_restore/",
  ],
  "P0-027": [
    "docs/operations/failover_simulation.md",
    "docs/evidence/failover/",
  ],
  "P0-028": [
    "docs/operations/pre_pilot_signoff_matrix.md",
    "docs/operations/pre_pilot_signoff_decisions.md",
  ],
};

function ensurePriorityFromId(id: string): string {
  return id.split("-")[0];
}

function isSubtask(id: string): boolean {
  return /^P\d{1,3}-\d{3}-[A-Z]$/.test(id);
}

async function resolveCandidatePath(relativePath: string): Promise<string> {
  const candidates = [
    path.join(process.cwd(), relativePath),
    path.join(process.cwd(), "..", relativePath),
  ];

  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // continue
    }
  }

  return candidates[0];
}

function parseList(value: string): string[] {
  if (!value) return [];
  const inlinePaths = value.match(/`([^`]+)`/g) ?? [];
  if (inlinePaths.length > 0) {
    return inlinePaths.map((entry) => entry.slice(1, -1));
  }

  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function parseChecklistLine(line: string): BacklogTask | null {
  const match = line.match(TASK_LINE_RE);
  if (!match) return null;

  const isDone = match[1].toLowerCase() !== CHECKBOX_OPEN;
  const itemId = match[2];
  if (!itemId) return null;

  const rawContent = match[3] ?? "";
  const segments = rawContent.split("|").map((segment) => segment.trim());
  const title = segments[0]?.trim() || "";
  const ownerSegment = segments.find((segment) => OWNER_RE.test(segment))?.match(OWNER_RE)?.[1] ?? "";
  const anchorSegment = segments.find((segment) => ANCHOR_RE.test(segment))?.match(ANCHOR_RE)?.[1] ?? "";
  const exitSegment = segments.find((segment) => EXIT_RE.test(segment))?.match(EXIT_RE)?.[1] ?? "";

  return {
    id: itemId,
    priority: ensurePriorityFromId(itemId),
    title,
    owner: ownerSegment,
    anchors: parseList(anchorSegment),
    exit: exitSegment,
    done: isDone,
    isSubtask: isSubtask(itemId),
    rawLine: line,
  };
}

function mergeArtifactPath(pathValue: string, artifacts: Map<string, Set<string>>, taskId: string): void {
  if (!artifacts.has(pathValue)) {
    artifacts.set(pathValue, new Set([taskId]));
    return;
  }
  artifacts.get(pathValue)?.add(taskId);
}

async function describeArtifactStatus(artifactPath: string): Promise<{ status: EvidenceArtifact["status"]; lastUpdatedAt: string | null }> {
  try {
    const source = await resolveCandidatePath(artifactPath);
    const stat = await fs.stat(source);
    return {
      status: "present",
      lastUpdatedAt: stat.mtime.toISOString(),
    };
  } catch {
    return {
      status: "missing",
      lastUpdatedAt: null,
    };
  }
}

export async function getReadinessSnapshot(): Promise<BacklogSummary> {
  const backlogSource = await resolveCandidatePath(BACKLOG_FILE);
  const backlogText = await fs.readFile(backlogSource, "utf8");
  const lines = backlogText.split(/\r?\n/);

  const allTasks: BacklogTask[] = [];
  for (const line of lines) {
    const item = parseChecklistLine(line);
    if (item) {
      allTasks.push(item);
    }
  }

  const openTopLevel: BacklogTask[] = [];
  const openSubtasks: BacklogTask[] = [];
  const openTopLevelByPriority: Record<string, number> = {};
  const openAllByPriority: Record<string, number> = {};
  const doneAllByPriority: Record<string, number> = {};
  const totalTopLevelByPriority: Record<string, number> = {};
  const totalAllByPriority: Record<string, number> = {};

  const artifactMap = new Map<string, Set<string>>();

  for (const task of allTasks) {
    const priority = task.priority;
    totalAllByPriority[priority] = (totalAllByPriority[priority] ?? 0) + 1;
    if (task.done) {
      doneAllByPriority[priority] = (doneAllByPriority[priority] ?? 0) + 1;
    } else {
      openAllByPriority[priority] = (openAllByPriority[priority] ?? 0) + 1;
    }

    if (!task.isSubtask) {
      totalTopLevelByPriority[priority] = (totalTopLevelByPriority[priority] ?? 0) + 1;
      if (task.done) {
        // no-op
      } else {
        openTopLevel.push(task);
        openTopLevelByPriority[priority] = (openTopLevelByPriority[priority] ?? 0) + 1;
      }
    } else if (!task.done) {
      openSubtasks.push(task);
    }

    const parentId = task.id.split("-").slice(0, 2).join("-");
    const hints = P0_EVIDENCE_HINTS[parentId];
    const configuredAnchors = task.anchors.length > 0 ? task.anchors : [];
    for (const anchor of [...configuredAnchors, ...(hints ?? [])]) {
      if (anchor) {
        mergeArtifactPath(anchor, artifactMap, task.id);
      }
    }
  }

  const evidenceArtifacts = await Promise.all(
    Array.from(artifactMap.entries()).map(async ([artifactPath, taskIds]) => {
      const status = await describeArtifactStatus(artifactPath);
      return {
        path: artifactPath,
        status: status.status,
        lastUpdatedAt: status.lastUpdatedAt,
        relatedTaskIds: Array.from(taskIds).sort(),
      };
    })
  );

  let sourceUpdatedAt: string | null = null;
  try {
    const sourceStat = await fs.stat(backlogSource);
    sourceUpdatedAt = sourceStat.mtime.toISOString();
  } catch {
    sourceUpdatedAt = null;
  }

  return {
    generatedAt: new Date().toISOString(),
    sourceFile: "tasks/09_master_change_backlog_p0_p4.md",
    sourceUpdatedAt,
    counts: {
      openAll: {
        P0: openAllByPriority.P0 ?? 0,
        P1: openAllByPriority.P1 ?? 0,
        P2: openAllByPriority.P2 ?? 0,
        P3: openAllByPriority.P3 ?? 0,
        P4: openAllByPriority.P4 ?? 0,
      },
      doneAll: {
        P0: doneAllByPriority.P0 ?? 0,
        P1: doneAllByPriority.P1 ?? 0,
        P2: doneAllByPriority.P2 ?? 0,
        P3: doneAllByPriority.P3 ?? 0,
        P4: doneAllByPriority.P4 ?? 0,
      },
      totalTopLevel: {
        P0: totalTopLevelByPriority.P0 ?? 0,
        P1: totalTopLevelByPriority.P1 ?? 0,
        P2: totalTopLevelByPriority.P2 ?? 0,
        P3: totalTopLevelByPriority.P3 ?? 0,
        P4: totalTopLevelByPriority.P4 ?? 0,
      },
      totalAll: {
        P0: totalAllByPriority.P0 ?? 0,
        P1: totalAllByPriority.P1 ?? 0,
        P2: totalAllByPriority.P2 ?? 0,
        P3: totalAllByPriority.P3 ?? 0,
        P4: totalAllByPriority.P4 ?? 0,
      },
      openTopLevelByPriority: {
        P0: openTopLevelByPriority.P0 ?? 0,
        P1: openTopLevelByPriority.P1 ?? 0,
        P2: openTopLevelByPriority.P2 ?? 0,
        P3: openTopLevelByPriority.P3 ?? 0,
        P4: openTopLevelByPriority.P4 ?? 0,
      },
    },
    openTopLevel: openTopLevel.sort((a, b) => (a.id > b.id ? 1 : -1)),
    openSubtasks: openSubtasks.sort((a, b) => (a.id > b.id ? 1 : -1)),
    evidenceArtifacts: evidenceArtifacts.sort((a, b) => a.path.localeCompare(b.path)),
  };
}
