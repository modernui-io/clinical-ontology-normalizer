"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  Webhook,
  Plus,
  Trash2,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ExternalLink,
  Copy,
  Eye,
  EyeOff,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";

// ============================================================================
// Types
// ============================================================================

interface WebhookItem {
  id: string;
  name: string;
  url: string;
  event_types: string[];
  is_active: boolean;
  created_at: string;
  last_triggered_at: string | null;
  failure_count: number;
}

interface DeliveryLog {
  id: string;
  notification_id: string;
  channel: string;
  status: string;
  attempt: number;
  timestamp: string;
  error_message: string | null;
  response_code: number | null;
}

const EVENT_TYPES = [
  { value: "drug_interaction", label: "Drug Interaction", category: "Critical" },
  { value: "coding_error", label: "Coding Error", category: "Critical" },
  { value: "critical_lab", label: "Critical Lab", category: "Critical" },
  { value: "system_error", label: "System Error", category: "Critical" },
  { value: "document_processed", label: "Document Processed", category: "Info" },
  { value: "export_ready", label: "Export Ready", category: "Info" },
  { value: "patient_updated", label: "Patient Updated", category: "Info" },
  { value: "job_complete", label: "Job Complete", category: "Info" },
  { value: "security_alert", label: "Security Alert", category: "Security" },
];

// ============================================================================
// Form Schema
// ============================================================================

const webhookSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  url: z.string().url("Must be a valid URL"),
  secret: z.string().optional(),
  event_types: z.array(z.string()).min(1, "Select at least one event type"),
});

type WebhookFormData = z.infer<typeof webhookSchema>;

// ============================================================================
// Webhooks Settings Page
// ============================================================================

export default function WebhooksSettingsPage() {
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [deliveryLogs, setDeliveryLogs] = useState<DeliveryLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isTesting, setIsTesting] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const form = useForm<WebhookFormData>({
    resolver: zodResolver(webhookSchema),
    defaultValues: {
      name: "",
      url: "",
      secret: "",
      event_types: [],
    },
  });

  // Fetch webhooks
  useEffect(() => {
    const fetchWebhooks = async () => {
      try {
        const response = await fetch(
          "/api/notifications/webhooks?user_id=demo-user"
        );
        if (response.ok) {
          const data = await response.json();
          setWebhooks(data.webhooks);
        }
      } catch (error) {
        console.error("Failed to fetch webhooks:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchWebhooks();
  }, []);

  // Fetch delivery logs
  const fetchDeliveryLogs = async () => {
    try {
      const response = await fetch(
        "/api/notifications/delivery-logs?channel=webhook&limit=50"
      );
      if (response.ok) {
        const data = await response.json();
        setDeliveryLogs(data.logs);
      }
    } catch (error) {
      console.error("Failed to fetch delivery logs:", error);
    }
  };

  const onCreateWebhook = async (data: WebhookFormData) => {
    setIsCreating(true);

    try {
      const response = await fetch(
        "/api/notifications/webhooks?user_id=demo-user",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      );

      if (response.ok) {
        const newWebhook = await response.json();
        setWebhooks((prev) => [...prev, newWebhook]);
        setShowCreateDialog(false);
        form.reset();
        toast.success("Webhook created", {
          description: `${data.name} has been created successfully.`,
        });
      } else {
        throw new Error("Failed to create webhook");
      }
    } catch (error) {
      toast.error("Failed to create webhook", {
        description: "Please check the URL and try again.",
      });
    } finally {
      setIsCreating(false);
    }
  };

  const onDeleteWebhook = async (webhookId: string) => {
    try {
      const response = await fetch(
        `/api/notifications/webhooks/${webhookId}?user_id=demo-user`,
        { method: "DELETE" }
      );

      if (response.ok) {
        setWebhooks((prev) => prev.filter((w) => w.id !== webhookId));
        toast.success("Webhook deleted");
      } else {
        throw new Error("Failed to delete webhook");
      }
    } catch (error) {
      toast.error("Failed to delete webhook");
    }
  };

  const onTestWebhook = async (webhookId: string) => {
    setIsTesting(webhookId);

    try {
      const response = await fetch(
        `/api/notifications/webhooks/${webhookId}/test?user_id=demo-user`,
        { method: "POST" }
      );

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          toast.success("Webhook test successful", {
            description: `Response time: ${result.response_time_ms}ms`,
          });
        } else {
          toast.error("Webhook test failed", {
            description: result.error_message || "No response from endpoint",
          });
        }
      } else {
        throw new Error("Failed to test webhook");
      }
    } catch (error) {
      toast.error("Failed to test webhook");
    } finally {
      setIsTesting(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container max-w-5xl py-8 px-4 md:px-6">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Webhook Settings</h1>
          <p className="text-muted-foreground mt-2">
            Configure custom webhooks to receive notifications.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => {
              fetchDeliveryLogs();
              setShowLogsDialog(true);
            }}
          >
            <Clock className="mr-2 h-4 w-4" />
            View Logs
          </Button>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Webhook
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onCreateWebhook)}>
                  <DialogHeader>
                    <DialogTitle>Create Webhook</DialogTitle>
                    <DialogDescription>
                      Configure a new webhook endpoint to receive notifications.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Name</FormLabel>
                          <FormControl>
                            <Input placeholder="My Webhook" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="url"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Endpoint URL</FormLabel>
                          <FormControl>
                            <Input
                              type="url"
                              placeholder="https://api.example.com/webhook"
                              {...field}
                            />
                          </FormControl>
                          <FormDescription>
                            The URL where notifications will be sent
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="secret"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Signing Secret (Optional)</FormLabel>
                          <FormControl>
                            <div className="relative">
                              <Input
                                type={showSecret ? "text" : "password"}
                                placeholder="Optional signing secret"
                                {...field}
                              />
                              <button
                                type="button"
                                onClick={() => setShowSecret(!showSecret)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                              >
                                {showSecret ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                          </FormControl>
                          <FormDescription>
                            Used to sign webhook payloads for verification
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="event_types"
                      render={() => (
                        <FormItem>
                          <FormLabel>Event Types</FormLabel>
                          <div className="space-y-4">
                            {["Critical", "Info", "Security"].map((category) => (
                              <div key={category}>
                                <Label className="text-xs text-muted-foreground uppercase tracking-wider">
                                  {category}
                                </Label>
                                <div className="grid grid-cols-2 gap-2 mt-1">
                                  {EVENT_TYPES.filter(
                                    (e) => e.category === category
                                  ).map((eventType) => (
                                    <FormField
                                      key={eventType.value}
                                      control={form.control}
                                      name="event_types"
                                      render={({ field }) => (
                                        <FormItem className="flex items-center space-x-2 space-y-0">
                                          <FormControl>
                                            <Checkbox
                                              checked={field.value?.includes(
                                                eventType.value
                                              )}
                                              onCheckedChange={(checked) => {
                                                const values = field.value || [];
                                                if (checked) {
                                                  field.onChange([
                                                    ...values,
                                                    eventType.value,
                                                  ]);
                                                } else {
                                                  field.onChange(
                                                    values.filter(
                                                      (v) => v !== eventType.value
                                                    )
                                                  );
                                                }
                                              }}
                                            />
                                          </FormControl>
                                          <FormLabel className="text-sm font-normal cursor-pointer">
                                            {eventType.label}
                                          </FormLabel>
                                        </FormItem>
                                      )}
                                    />
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <DialogFooter>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowCreateDialog(false)}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={isCreating}>
                      {isCreating ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        "Create Webhook"
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Webhooks List */}
      {webhooks.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Webhook className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No webhooks configured</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create a webhook to receive notifications at your own endpoints.
            </p>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Your First Webhook
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {webhooks.map((webhook) => (
            <Card key={webhook.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-md bg-muted">
                      <Webhook className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{webhook.name}</CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        <code className="text-xs bg-muted px-2 py-0.5 rounded">
                          {webhook.url.length > 50
                            ? `${webhook.url.substring(0, 50)}...`
                            : webhook.url}
                        </code>
                        <button
                          onClick={() => copyToClipboard(webhook.url)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Copy className="h-3 w-3" />
                        </button>
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {webhook.is_active ? (
                      <Badge variant="default" className="bg-green-500">
                        Active
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                    {webhook.failure_count > 0 && (
                      <Badge variant="destructive">
                        {webhook.failure_count} failures
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pb-3">
                <div className="flex flex-wrap gap-1 mb-3">
                  {webhook.event_types.map((type) => (
                    <Badge key={type} variant="outline" className="text-xs">
                      {EVENT_TYPES.find((e) => e.value === type)?.label || type}
                    </Badge>
                  ))}
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    Created: {new Date(webhook.created_at).toLocaleDateString()}
                  </span>
                  {webhook.last_triggered_at && (
                    <span>
                      Last triggered:{" "}
                      {new Date(webhook.last_triggered_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </CardContent>
              <CardFooter className="border-t pt-3">
                <div className="flex justify-between w-full">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onTestWebhook(webhook.id)}
                    disabled={isTesting === webhook.id}
                  >
                    {isTesting === webhook.id ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Test Webhook
                      </>
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => onDeleteWebhook(webhook.id)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Delivery Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>Webhook Delivery Logs</DialogTitle>
            <DialogDescription>
              Recent webhook delivery attempts and their status.
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[400px]">
            {deliveryLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Clock className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-muted-foreground">No delivery logs yet</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Attempt</TableHead>
                    <TableHead>Response</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveryLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell>
                        {log.status === "delivered" ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : log.status === "failed" ? (
                          <XCircle className="h-4 w-4 text-red-500" />
                        ) : (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {new Date(log.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell>{log.attempt}</TableCell>
                      <TableCell>
                        {log.response_code && (
                          <Badge
                            variant={
                              log.response_code < 400 ? "default" : "destructive"
                            }
                          >
                            {log.response_code}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                        {log.error_message || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Documentation Card */}
      <Card className="mt-8">
        <CardHeader>
          <CardTitle className="text-lg">Webhook Integration</CardTitle>
          <CardDescription>
            Information about webhook payload format and verification.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">Payload Format</h4>
            <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto">
              {JSON.stringify(
                {
                  event_type: "document_processed",
                  notification_id: "uuid",
                  subject: "Document Processing Complete",
                  body: "Your document has been processed...",
                  priority: "low",
                  timestamp: "2024-01-15T10:30:00Z",
                  metadata: {},
                },
                null,
                2
              )}
            </pre>
          </div>
          <div>
            <h4 className="font-medium mb-2">Signature Verification</h4>
            <p className="text-sm text-muted-foreground">
              If you configure a signing secret, webhook payloads will include an{" "}
              <code className="bg-muted px-1 py-0.5 rounded">
                X-Webhook-Signature
              </code>{" "}
              header with format{" "}
              <code className="bg-muted px-1 py-0.5 rounded">sha256=...</code>
              . Verify by computing HMAC-SHA256 of the JSON payload with your secret.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
