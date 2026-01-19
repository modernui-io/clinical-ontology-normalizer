"use client";

import { useState, useEffect, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  Bell,
  Mail,
  MessageSquare,
  Webhook,
  Monitor,
  Save,
  AlertTriangle,
  Clock,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";

// ============================================================================
// Types
// ============================================================================

interface ChannelPreferences {
  slack: boolean;
  email: boolean;
  webhook: boolean;
  in_app: boolean;
}

interface TypePreferences {
  drug_interaction: boolean;
  coding_error: boolean;
  critical_lab: boolean;
  document_processed: boolean;
  export_ready: boolean;
  daily_summary: boolean;
  security_alert: boolean;
}

interface NotificationPreferences {
  channels: ChannelPreferences;
  types: TypePreferences;
  slack_webhook_url: string | null;
  email_address: string | null;
  digest_frequency: string;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
}

// ============================================================================
// Form Schema
// ============================================================================

const preferencesSchema = z.object({
  slackEnabled: z.boolean(),
  emailEnabled: z.boolean(),
  webhookEnabled: z.boolean(),
  inAppEnabled: z.boolean(),
  slackWebhookUrl: z.string().url().optional().or(z.literal("")),
  emailAddress: z.string().email().optional().or(z.literal("")),
  digestFrequency: z.enum(["none", "daily", "weekly"]),
  quietHoursStart: z.number().min(0).max(23).optional().nullable(),
  quietHoursEnd: z.number().min(0).max(23).optional().nullable(),
  drugInteraction: z.boolean(),
  codingError: z.boolean(),
  criticalLab: z.boolean(),
  documentProcessed: z.boolean(),
  exportReady: z.boolean(),
  dailySummary: z.boolean(),
  securityAlert: z.boolean(),
});

type PreferencesFormData = z.infer<typeof preferencesSchema>;

// ============================================================================
// Toggle Component
// ============================================================================

function ToggleItem({
  id,
  label,
  description,
  checked,
  onChange,
  icon: Icon,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon?: React.ElementType;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-start gap-3">
        {Icon && (
          <div className="mt-0.5 p-2 rounded-md bg-muted">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
        <div className="space-y-0.5">
          <Label htmlFor={id} className="text-sm font-medium cursor-pointer">
            {label}
          </Label>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

// ============================================================================
// Notification Settings Page
// ============================================================================

export default function NotificationSettingsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const form = useForm<PreferencesFormData>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: {
      slackEnabled: false,
      emailEnabled: true,
      webhookEnabled: false,
      inAppEnabled: true,
      slackWebhookUrl: "",
      emailAddress: "",
      digestFrequency: "daily",
      quietHoursStart: null,
      quietHoursEnd: null,
      drugInteraction: true,
      codingError: true,
      criticalLab: true,
      documentProcessed: true,
      exportReady: true,
      dailySummary: false,
      securityAlert: true,
    },
  });

  const slackEnabled = form.watch("slackEnabled");
  const emailEnabled = form.watch("emailEnabled");

  // Load preferences
  useEffect(() => {
    const fetchPreferences = async () => {
      try {
        const response = await fetch(
          "http://localhost:8000/notifications/preferences?user_id=demo-user"
        );
        if (response.ok) {
          const data: NotificationPreferences = await response.json();
          form.reset({
            slackEnabled: data.channels.slack,
            emailEnabled: data.channels.email,
            webhookEnabled: data.channels.webhook,
            inAppEnabled: data.channels.in_app,
            slackWebhookUrl: data.slack_webhook_url || "",
            emailAddress: data.email_address || "",
            digestFrequency: data.digest_frequency as "none" | "daily" | "weekly",
            quietHoursStart: data.quiet_hours_start,
            quietHoursEnd: data.quiet_hours_end,
            drugInteraction: data.types.drug_interaction,
            codingError: data.types.coding_error,
            criticalLab: data.types.critical_lab,
            documentProcessed: data.types.document_processed,
            exportReady: data.types.export_ready,
            dailySummary: data.types.daily_summary,
            securityAlert: data.types.security_alert,
          });
        }
      } catch (error) {
        console.error("Failed to fetch preferences:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPreferences();
  }, [form]);

  const onSubmit = async (data: PreferencesFormData) => {
    setIsSaving(true);

    try {
      const preferences: NotificationPreferences = {
        channels: {
          slack: data.slackEnabled,
          email: data.emailEnabled,
          webhook: data.webhookEnabled,
          in_app: data.inAppEnabled,
        },
        types: {
          drug_interaction: data.drugInteraction,
          coding_error: data.codingError,
          critical_lab: data.criticalLab,
          document_processed: data.documentProcessed,
          export_ready: data.exportReady,
          daily_summary: data.dailySummary,
          security_alert: data.securityAlert,
        },
        slack_webhook_url: data.slackWebhookUrl || null,
        email_address: data.emailAddress || null,
        digest_frequency: data.digestFrequency,
        quiet_hours_start: data.quietHoursStart ?? null,
        quiet_hours_end: data.quietHoursEnd ?? null,
      };

      const response = await fetch(
        "http://localhost:8000/notifications/preferences?user_id=demo-user",
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(preferences),
        }
      );

      if (response.ok) {
        toast.success("Preferences saved", {
          description: "Your notification preferences have been updated.",
        });
      } else {
        throw new Error("Failed to save preferences");
      }
    } catch (error) {
      toast.error("Failed to save", {
        description: "Please try again later.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container max-w-4xl py-8 px-4 md:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Notification Settings</h1>
        <p className="text-muted-foreground mt-2">
          Configure how and when you receive notifications.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Channel Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Notification Channels
              </CardTitle>
              <CardDescription>
                Choose which channels you want to receive notifications on.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              <FormField
                control={form.control}
                name="inAppEnabled"
                render={({ field }) => (
                  <ToggleItem
                    id="in-app"
                    label="In-App Notifications"
                    description="Show notifications within the application"
                    checked={field.value}
                    onChange={field.onChange}
                    icon={Monitor}
                  />
                )}
              />
              <Separator />
              <FormField
                control={form.control}
                name="emailEnabled"
                render={({ field }) => (
                  <ToggleItem
                    id="email"
                    label="Email Notifications"
                    description="Receive notifications via email"
                    checked={field.value}
                    onChange={field.onChange}
                    icon={Mail}
                  />
                )}
              />
              {emailEnabled && (
                <div className="ml-12 pb-3">
                  <FormField
                    control={form.control}
                    name="emailAddress"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email Address</FormLabel>
                        <FormControl>
                          <Input
                            type="email"
                            placeholder="your@email.com"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}
              <Separator />
              <FormField
                control={form.control}
                name="slackEnabled"
                render={({ field }) => (
                  <ToggleItem
                    id="slack"
                    label="Slack Notifications"
                    description="Send notifications to a Slack channel"
                    checked={field.value}
                    onChange={field.onChange}
                    icon={MessageSquare}
                  />
                )}
              />
              {slackEnabled && (
                <div className="ml-12 pb-3">
                  <FormField
                    control={form.control}
                    name="slackWebhookUrl"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Slack Webhook URL</FormLabel>
                        <FormControl>
                          <Input
                            type="url"
                            placeholder="https://hooks.slack.com/services/..."
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Create an incoming webhook in your Slack workspace
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}
              <Separator />
              <FormField
                control={form.control}
                name="webhookEnabled"
                render={({ field }) => (
                  <ToggleItem
                    id="webhook"
                    label="Custom Webhooks"
                    description="Send notifications to custom webhook endpoints"
                    checked={field.value}
                    onChange={field.onChange}
                    icon={Webhook}
                  />
                )}
              />
            </CardContent>
          </Card>

          {/* Alert Type Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Alert Types
              </CardTitle>
              <CardDescription>
                Choose which types of alerts you want to receive.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              <div className="mb-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Critical Alerts
                </h4>
              </div>
              <FormField
                control={form.control}
                name="drugInteraction"
                render={({ field }) => (
                  <ToggleItem
                    id="drug-interaction"
                    label="Drug Interaction Alerts"
                    description="Notifications about potential drug-drug interactions"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <FormField
                control={form.control}
                name="criticalLab"
                render={({ field }) => (
                  <ToggleItem
                    id="critical-lab"
                    label="Critical Lab Values"
                    description="Alerts for abnormal or critical laboratory results"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <FormField
                control={form.control}
                name="codingError"
                render={({ field }) => (
                  <ToggleItem
                    id="coding-error"
                    label="Coding Error Alerts"
                    description="Notifications about potential coding errors"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <FormField
                control={form.control}
                name="securityAlert"
                render={({ field }) => (
                  <ToggleItem
                    id="security-alert"
                    label="Security Alerts"
                    description="Important security notifications (recommended)"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <Separator className="my-4" />
              <div className="mb-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Informational Notifications
                </h4>
              </div>
              <FormField
                control={form.control}
                name="documentProcessed"
                render={({ field }) => (
                  <ToggleItem
                    id="document-processed"
                    label="Document Processed"
                    description="Notifications when document processing completes"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <FormField
                control={form.control}
                name="exportReady"
                render={({ field }) => (
                  <ToggleItem
                    id="export-ready"
                    label="Export Ready"
                    description="Notifications when data exports are ready"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <FormField
                control={form.control}
                name="dailySummary"
                render={({ field }) => (
                  <ToggleItem
                    id="daily-summary"
                    label="Daily Summary"
                    description="Receive a daily activity summary"
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </CardContent>
          </Card>

          {/* Digest and Quiet Hours */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Schedule Settings
              </CardTitle>
              <CardDescription>
                Configure digest frequency and quiet hours.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <FormField
                control={form.control}
                name="digestFrequency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Digest Frequency</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select frequency" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="none">No digest</SelectItem>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      How often to receive summary digests
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="quietHoursStart"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Quiet Hours Start</FormLabel>
                      <Select
                        onValueChange={(value) =>
                          field.onChange(value ? parseInt(value) : null)
                        }
                        value={field.value?.toString() || ""}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Not set" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="">Not set</SelectItem>
                          {Array.from({ length: 24 }, (_, i) => (
                            <SelectItem key={i} value={i.toString()}>
                              {i.toString().padStart(2, "0")}:00
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="quietHoursEnd"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Quiet Hours End</FormLabel>
                      <Select
                        onValueChange={(value) =>
                          field.onChange(value ? parseInt(value) : null)
                        }
                        value={field.value?.toString() || ""}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Not set" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="">Not set</SelectItem>
                          {Array.from({ length: 24 }, (_, i) => (
                            <SelectItem key={i} value={i.toString()}>
                              {i.toString().padStart(2, "0")}:00
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <p className="text-sm text-muted-foreground">
                Non-critical notifications will be suppressed during quiet hours.
                Critical alerts will still be delivered.
              </p>
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save Preferences
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>
        </form>
      </Form>
    </div>
  );
}
