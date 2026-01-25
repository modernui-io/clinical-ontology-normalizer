"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import {
  Bell,
  Plus,
  Settings,
  Trash2,
  Copy,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle,
  Clock,
  Users,
  Activity,
  TrendingUp,
  Mail,
  MessageSquare,
  Phone,
} from "lucide-react";

// Types
interface AlertRule {
  id: string;
  name: string;
  description: string;
  riskModel: string;
  condition: {
    metric: string;
    operator: ">" | ">=" | "<" | "<=" | "==" | "between";
    threshold: number;
    thresholdHigh?: number;
  };
  severity: "low" | "medium" | "high" | "critical";
  enabled: boolean;
  notifications: {
    email: boolean;
    sms: boolean;
    inApp: boolean;
    slack: boolean;
  };
  recipients: string[];
  cooldownMinutes: number;
  createdAt: string;
  lastTriggered?: string;
  triggerCount: number;
}

interface AlertHistory {
  id: string;
  ruleId: string;
  ruleName: string;
  patientId: string;
  patientName: string;
  riskScore: number;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  triggeredAt: string;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
}

// Mock data
const mockRules: AlertRule[] = [
  {
    id: "rule-1",
    name: "High Mortality Risk",
    description: "Alert when 30-day mortality risk exceeds 80%",
    riskModel: "mortality-30day",
    condition: { metric: "mortality_risk", operator: ">=", threshold: 0.8 },
    severity: "critical",
    enabled: true,
    notifications: { email: true, sms: true, inApp: true, slack: true },
    recipients: ["care-team@hospital.org", "palliative@hospital.org"],
    cooldownMinutes: 60,
    createdAt: "2026-01-10T10:00:00Z",
    lastTriggered: "2026-01-24T08:30:00Z",
    triggerCount: 47,
  },
  {
    id: "rule-2",
    name: "Readmission Risk Elevated",
    description: "Alert when 30-day readmission risk exceeds 60%",
    riskModel: "readmission-30day",
    condition: { metric: "readmission_risk", operator: ">=", threshold: 0.6 },
    severity: "high",
    enabled: true,
    notifications: { email: true, sms: false, inApp: true, slack: true },
    recipients: ["discharge-planning@hospital.org"],
    cooldownMinutes: 120,
    createdAt: "2026-01-12T14:00:00Z",
    lastTriggered: "2026-01-24T06:15:00Z",
    triggerCount: 128,
  },
  {
    id: "rule-3",
    name: "Sepsis Risk Warning",
    description: "Alert when sepsis risk score exceeds 70%",
    riskModel: "sepsis-early",
    condition: { metric: "sepsis_risk", operator: ">=", threshold: 0.7 },
    severity: "critical",
    enabled: true,
    notifications: { email: true, sms: true, inApp: true, slack: true },
    recipients: ["rapid-response@hospital.org", "icu@hospital.org"],
    cooldownMinutes: 30,
    createdAt: "2026-01-15T09:00:00Z",
    lastTriggered: "2026-01-24T10:45:00Z",
    triggerCount: 23,
  },
  {
    id: "rule-4",
    name: "Fall Risk Moderate",
    description: "Alert when fall risk is between 40-60%",
    riskModel: "fall-risk",
    condition: { metric: "fall_risk", operator: "between", threshold: 0.4, thresholdHigh: 0.6 },
    severity: "medium",
    enabled: false,
    notifications: { email: true, sms: false, inApp: true, slack: false },
    recipients: ["nursing@hospital.org"],
    cooldownMinutes: 240,
    createdAt: "2026-01-18T11:00:00Z",
    triggerCount: 89,
  },
  {
    id: "rule-5",
    name: "Deterioration Watch",
    description: "Alert when clinical deterioration score increases rapidly",
    riskModel: "deterioration",
    condition: { metric: "deterioration_score", operator: ">", threshold: 0.5 },
    severity: "high",
    enabled: true,
    notifications: { email: true, sms: false, inApp: true, slack: true },
    recipients: ["attending@hospital.org"],
    cooldownMinutes: 60,
    createdAt: "2026-01-20T16:00:00Z",
    lastTriggered: "2026-01-24T09:20:00Z",
    triggerCount: 34,
  },
];

const mockAlertHistory: AlertHistory[] = [
  {
    id: "alert-1",
    ruleId: "rule-3",
    ruleName: "Sepsis Risk Warning",
    patientId: "P-10045",
    patientName: "John Smith",
    riskScore: 0.78,
    severity: "critical",
    message: "Sepsis risk score 78% exceeds threshold of 70%",
    triggeredAt: "2026-01-24T10:45:00Z",
    acknowledged: true,
    acknowledgedBy: "Dr. Sarah Johnson",
    acknowledgedAt: "2026-01-24T10:52:00Z",
  },
  {
    id: "alert-2",
    ruleId: "rule-1",
    ruleName: "High Mortality Risk",
    patientId: "P-10089",
    patientName: "Mary Williams",
    riskScore: 0.85,
    severity: "critical",
    message: "30-day mortality risk 85% exceeds threshold of 80%",
    triggeredAt: "2026-01-24T08:30:00Z",
    acknowledged: true,
    acknowledgedBy: "Dr. Michael Chen",
    acknowledgedAt: "2026-01-24T08:45:00Z",
  },
  {
    id: "alert-3",
    ruleId: "rule-5",
    ruleName: "Deterioration Watch",
    patientId: "P-10123",
    patientName: "Robert Brown",
    riskScore: 0.62,
    severity: "high",
    message: "Clinical deterioration score 62% exceeds threshold of 50%",
    triggeredAt: "2026-01-24T09:20:00Z",
    acknowledged: false,
  },
  {
    id: "alert-4",
    ruleId: "rule-2",
    ruleName: "Readmission Risk Elevated",
    patientId: "P-10067",
    patientName: "Patricia Davis",
    riskScore: 0.68,
    severity: "high",
    message: "30-day readmission risk 68% exceeds threshold of 60%",
    triggeredAt: "2026-01-24T06:15:00Z",
    acknowledged: true,
    acknowledgedBy: "Nurse Linda Thompson",
    acknowledgedAt: "2026-01-24T06:30:00Z",
  },
  {
    id: "alert-5",
    ruleId: "rule-2",
    ruleName: "Readmission Risk Elevated",
    patientId: "P-10091",
    patientName: "James Wilson",
    riskScore: 0.72,
    severity: "high",
    message: "30-day readmission risk 72% exceeds threshold of 60%",
    triggeredAt: "2026-01-24T04:00:00Z",
    acknowledged: true,
    acknowledgedBy: "Dr. Emily Rodriguez",
    acknowledgedAt: "2026-01-24T04:20:00Z",
  },
];

const riskModels = [
  { id: "mortality-30day", name: "30-Day Mortality Risk" },
  { id: "readmission-30day", name: "30-Day Readmission Risk" },
  { id: "sepsis-early", name: "Early Sepsis Detection" },
  { id: "fall-risk", name: "Fall Risk Assessment" },
  { id: "deterioration", name: "Clinical Deterioration" },
  { id: "aki-risk", name: "Acute Kidney Injury Risk" },
  { id: "vte-risk", name: "VTE Risk Score" },
];

const severityColors = {
  low: "bg-blue-100 text-blue-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

export default function AlertRulesPage() {
  const [rules, setRules] = useState<AlertRule[]>(mockRules);
  const [alertHistory] = useState<AlertHistory[]>(mockAlertHistory);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedRule, setSelectedRule] = useState<AlertRule | null>(null);
  const [newRule, setNewRule] = useState<Partial<AlertRule>>({
    name: "",
    description: "",
    riskModel: "",
    condition: { metric: "", operator: ">=", threshold: 0.5 },
    severity: "medium",
    notifications: { email: true, sms: false, inApp: true, slack: false },
    recipients: [],
    cooldownMinutes: 60,
  });

  const toggleRule = (ruleId: string) => {
    setRules(rules.map(r =>
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    ));
  };

  const deleteRule = (ruleId: string) => {
    setRules(rules.filter(r => r.id !== ruleId));
  };

  const duplicateRule = (rule: AlertRule) => {
    const newRuleCopy: AlertRule = {
      ...rule,
      id: `rule-${Date.now()}`,
      name: `${rule.name} (Copy)`,
      createdAt: new Date().toISOString(),
      triggerCount: 0,
      lastTriggered: undefined,
    };
    setRules([...rules, newRuleCopy]);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const unacknowledgedCount = alertHistory.filter(a => !a.acknowledged).length;
  const activeRulesCount = rules.filter(r => r.enabled).length;
  const totalTriggers = rules.reduce((sum, r) => sum + r.triggerCount, 0);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Alert Rules</h1>
          <p className="text-muted-foreground">
            Configure risk-based alerts to notify care teams
          </p>
        </div>
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Rule
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Alert Rule</DialogTitle>
              <DialogDescription>
                Define conditions and notifications for risk-based alerts
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Rule Name</Label>
                  <Input
                    value={newRule.name}
                    onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                    placeholder="e.g., High Mortality Risk Alert"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Risk Model</Label>
                  <Select
                    value={newRule.riskModel}
                    onValueChange={(v) => setNewRule({ ...newRule, riskModel: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {riskModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea
                  value={newRule.description}
                  onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
                  placeholder="Describe when and why this alert should fire"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Operator</Label>
                  <Select
                    value={newRule.condition?.operator}
                    onValueChange={(v) =>
                      setNewRule({
                        ...newRule,
                        condition: { ...newRule.condition!, operator: v as AlertRule["condition"]["operator"] },
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value=">=">Greater than or equal</SelectItem>
                      <SelectItem value=">">Greater than</SelectItem>
                      <SelectItem value="<=">Less than or equal</SelectItem>
                      <SelectItem value="<">Less than</SelectItem>
                      <SelectItem value="==">Equal to</SelectItem>
                      <SelectItem value="between">Between</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Threshold ({Math.round((newRule.condition?.threshold || 0.5) * 100)}%)</Label>
                  <Slider
                    value={[(newRule.condition?.threshold || 0.5) * 100]}
                    onValueChange={([v]) =>
                      setNewRule({
                        ...newRule,
                        condition: { ...newRule.condition!, threshold: v / 100 },
                      })
                    }
                    min={0}
                    max={100}
                    step={5}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Severity</Label>
                  <Select
                    value={newRule.severity}
                    onValueChange={(v) => setNewRule({ ...newRule, severity: v as AlertRule["severity"] })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Notification Channels</Label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <Switch
                      checked={newRule.notifications?.email}
                      onCheckedChange={(c) =>
                        setNewRule({
                          ...newRule,
                          notifications: { ...newRule.notifications!, email: c },
                        })
                      }
                    />
                    <Mail className="h-4 w-4" />
                    Email
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch
                      checked={newRule.notifications?.sms}
                      onCheckedChange={(c) =>
                        setNewRule({
                          ...newRule,
                          notifications: { ...newRule.notifications!, sms: c },
                        })
                      }
                    />
                    <Phone className="h-4 w-4" />
                    SMS
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch
                      checked={newRule.notifications?.inApp}
                      onCheckedChange={(c) =>
                        setNewRule({
                          ...newRule,
                          notifications: { ...newRule.notifications!, inApp: c },
                        })
                      }
                    />
                    <Bell className="h-4 w-4" />
                    In-App
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch
                      checked={newRule.notifications?.slack}
                      onCheckedChange={(c) =>
                        setNewRule({
                          ...newRule,
                          notifications: { ...newRule.notifications!, slack: c },
                        })
                      }
                    />
                    <MessageSquare className="h-4 w-4" />
                    Slack
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Recipients (comma-separated emails)</Label>
                  <Input
                    value={newRule.recipients?.join(", ")}
                    onChange={(e) =>
                      setNewRule({
                        ...newRule,
                        recipients: e.target.value.split(",").map((s) => s.trim()),
                      })
                    }
                    placeholder="team@hospital.org, doctor@hospital.org"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Cooldown (minutes)</Label>
                  <Input
                    type="number"
                    value={newRule.cooldownMinutes}
                    onChange={(e) =>
                      setNewRule({ ...newRule, cooldownMinutes: parseInt(e.target.value) })
                    }
                    min={5}
                    max={1440}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={() => {
                const rule: AlertRule = {
                  id: `rule-${Date.now()}`,
                  name: newRule.name || "Untitled Rule",
                  description: newRule.description || "",
                  riskModel: newRule.riskModel || "",
                  condition: newRule.condition as AlertRule["condition"],
                  severity: newRule.severity as AlertRule["severity"],
                  enabled: true,
                  notifications: newRule.notifications as AlertRule["notifications"],
                  recipients: newRule.recipients || [],
                  cooldownMinutes: newRule.cooldownMinutes || 60,
                  createdAt: new Date().toISOString(),
                  triggerCount: 0,
                };
                setRules([...rules, rule]);
                setCreateDialogOpen(false);
              }}>
                Create Rule
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Active Rules</p>
                <p className="text-2xl font-bold">{activeRulesCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Unacknowledged</p>
                <p className="text-2xl font-bold">{unacknowledgedCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Total Triggers (7d)</p>
                <p className="text-2xl font-bold">{totalTriggers}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Teams Notified</p>
                <p className="text-2xl font-bold">8</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="rules">
        <TabsList>
          <TabsTrigger value="rules">
            <Settings className="h-4 w-4 mr-2" />
            Rules Configuration
          </TabsTrigger>
          <TabsTrigger value="history">
            <Clock className="h-4 w-4 mr-2" />
            Alert History
            {unacknowledgedCount > 0 && (
              <Badge variant="destructive" className="ml-2">
                {unacknowledgedCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Configured Rules</CardTitle>
              <CardDescription>
                Manage risk threshold rules and notification settings
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Rule Name</TableHead>
                    <TableHead>Risk Model</TableHead>
                    <TableHead>Condition</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Notifications</TableHead>
                    <TableHead>Triggers</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rules.map((rule) => (
                    <TableRow key={rule.id}>
                      <TableCell>
                        <Switch
                          checked={rule.enabled}
                          onCheckedChange={() => toggleRule(rule.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{rule.name}</p>
                          <p className="text-sm text-muted-foreground truncate max-w-[200px]">
                            {rule.description}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {riskModels.find((m) => m.id === rule.riskModel)?.name || rule.riskModel}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <code className="text-sm">
                          {rule.condition.operator === "between"
                            ? `${(rule.condition.threshold * 100).toFixed(0)}% - ${((rule.condition.thresholdHigh || 0) * 100).toFixed(0)}%`
                            : `${rule.condition.operator} ${(rule.condition.threshold * 100).toFixed(0)}%`}
                        </code>
                      </TableCell>
                      <TableCell>
                        <Badge className={severityColors[rule.severity]}>
                          {rule.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {rule.notifications.email && <Mail className="h-4 w-4 text-muted-foreground" />}
                          {rule.notifications.sms && <Phone className="h-4 w-4 text-muted-foreground" />}
                          {rule.notifications.inApp && <Bell className="h-4 w-4 text-muted-foreground" />}
                          {rule.notifications.slack && <MessageSquare className="h-4 w-4 text-muted-foreground" />}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <TrendingUp className="h-4 w-4 text-muted-foreground" />
                          {rule.triggerCount}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setSelectedRule(rule)}
                          >
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => duplicateRule(rule)}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteRule(rule.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Alerts</CardTitle>
              <CardDescription>
                View and acknowledge triggered alerts
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>Risk Score</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {alertHistory.map((alert) => (
                    <TableRow key={alert.id} className={!alert.acknowledged ? "bg-red-50" : ""}>
                      <TableCell>
                        {alert.acknowledged ? (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                          <AlertTriangle className="h-5 w-5 text-orange-500" />
                        )}
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="text-sm">{formatDate(alert.triggeredAt)}</p>
                          {alert.acknowledgedAt && (
                            <p className="text-xs text-muted-foreground">
                              Ack: {formatDate(alert.acknowledgedAt)}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{alert.patientName}</p>
                          <p className="text-sm text-muted-foreground">{alert.patientId}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{alert.ruleName}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={severityColors[alert.severity]}>
                          {(alert.riskScore * 100).toFixed(0)}%
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <p className="text-sm max-w-[250px] truncate">{alert.message}</p>
                        {alert.acknowledgedBy && (
                          <p className="text-xs text-muted-foreground">
                            by {alert.acknowledgedBy}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        {!alert.acknowledged && (
                          <Button size="sm" variant="outline">
                            Acknowledge
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
