"use client";

/**
 * SMART on FHIR Consent Page
 *
 * Displays the authorization consent screen showing:
 * - App name and details
 * - Requested scopes
 * - Patient context (if EHR launch)
 * - Approve/Deny buttons
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, AlertCircle, Shield, User, FileText, Activity } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AppInfo {
  app_name: string;
  client_id: string;
}

interface AuthorizationRequest {
  client_id: string;
  redirect_uri: string;
  scope: string;
  state: string;
  code_challenge?: string;
  code_challenge_method?: string;
  patient_id?: string;
  encounter_id?: string;
}

// Map scopes to human-readable descriptions
const SCOPE_DESCRIPTIONS: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
  "openid": { label: "OpenID", icon: <Shield className="h-4 w-4" />, description: "Verify your identity" },
  "fhirUser": { label: "FHIR User", icon: <User className="h-4 w-4" />, description: "Access your user profile" },
  "launch/patient": { label: "Patient Context", icon: <User className="h-4 w-4" />, description: "Know which patient you're viewing" },
  "launch/encounter": { label: "Encounter Context", icon: <Activity className="h-4 w-4" />, description: "Know which encounter you're in" },
  "patient/*.read": { label: "Read Patient Data", icon: <FileText className="h-4 w-4" />, description: "Read all patient health records" },
  "patient/*.write": { label: "Write Patient Data", icon: <FileText className="h-4 w-4" />, description: "Modify patient health records" },
  "patient/Patient.read": { label: "Read Demographics", icon: <User className="h-4 w-4" />, description: "Read patient demographics" },
  "patient/Observation.read": { label: "Read Observations", icon: <Activity className="h-4 w-4" />, description: "Read lab results and vitals" },
  "patient/Condition.read": { label: "Read Conditions", icon: <FileText className="h-4 w-4" />, description: "Read diagnoses and conditions" },
  "offline_access": { label: "Offline Access", icon: <Shield className="h-4 w-4" />, description: "Access data when you're not logged in" },
};

export default function SMARTAuthorizePage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "ready" | "processing" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [authRequest, setAuthRequest] = useState<AuthorizationRequest | null>(null);

  useEffect(() => {
    async function loadAuthRequest() {
      try {
        const clientId = searchParams.get("client_id");
        const redirectUri = searchParams.get("redirect_uri");
        const scope = searchParams.get("scope");
        const state = searchParams.get("state");

        if (!clientId || !redirectUri || !scope || !state) {
          throw new Error("Missing required authorization parameters");
        }

        // Fetch app info
        const appResponse = await fetch(`${API_BASE_URL}/api/v1/smart-server/apps/${clientId}`);
        if (appResponse.ok) {
          const app = await appResponse.json();
          setAppInfo({ app_name: app.app_name, client_id: app.client_id });
        } else {
          setAppInfo({ app_name: "Unknown Application", client_id: clientId });
        }

        setAuthRequest({
          client_id: clientId,
          redirect_uri: redirectUri,
          scope,
          state,
          code_challenge: searchParams.get("code_challenge") || undefined,
          code_challenge_method: searchParams.get("code_challenge_method") || undefined,
          patient_id: searchParams.get("patient") || undefined,
          encounter_id: searchParams.get("encounter") || undefined,
        });

        setStatus("ready");
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Failed to load authorization request");
      }
    }

    loadAuthRequest();
  }, [searchParams]);

  async function handleApprove() {
    if (!authRequest) return;

    setStatus("processing");

    try {
      // Submit consent to backend
      const response = await fetch(`${API_BASE_URL}/api/v1/smart-server/authorize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: authRequest.client_id,
          redirect_uri: authRequest.redirect_uri,
          scope: authRequest.scope,
          state: authRequest.state,
          code_challenge: authRequest.code_challenge,
          code_challenge_method: authRequest.code_challenge_method,
          patient_id: authRequest.patient_id,
          encounter_id: authRequest.encounter_id,
          approved: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Authorization failed");
      }

      const result = await response.json();

      // Redirect to app with authorization code
      const redirectUrl = new URL(authRequest.redirect_uri);
      redirectUrl.searchParams.set("code", result.code);
      redirectUrl.searchParams.set("state", authRequest.state);
      window.location.href = redirectUrl.toString();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to authorize");
    }
  }

  function handleDeny() {
    if (!authRequest) return;

    // Redirect to app with error
    const redirectUrl = new URL(authRequest.redirect_uri);
    redirectUrl.searchParams.set("error", "access_denied");
    redirectUrl.searchParams.set("error_description", "User denied the authorization request");
    redirectUrl.searchParams.set("state", authRequest.state);
    window.location.href = redirectUrl.toString();
  }

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-lg">
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-muted-foreground">Loading authorization request...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <AlertCircle className="h-5 w-5" />
              Authorization Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const scopes = authRequest?.scope.split(" ") || [];

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Authorization Request
          </CardTitle>
          <CardDescription>
            <span className="font-semibold text-foreground">{appInfo?.app_name}</span> is requesting access to your health data
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {authRequest?.patient_id && (
            <div className="rounded-lg bg-muted p-3">
              <p className="text-sm text-muted-foreground">Patient Context</p>
              <p className="font-mono text-sm">{authRequest.patient_id}</p>
            </div>
          )}

          <div>
            <p className="text-sm font-medium mb-3">This application is requesting permission to:</p>
            <div className="space-y-2">
              {scopes.map((scope) => {
                const info = SCOPE_DESCRIPTIONS[scope] || {
                  label: scope,
                  icon: <FileText className="h-4 w-4" />,
                  description: scope,
                };
                return (
                  <div key={scope} className="flex items-start gap-3 p-2 rounded-lg bg-muted/50">
                    <div className="mt-0.5 text-muted-foreground">{info.icon}</div>
                    <div>
                      <p className="text-sm font-medium">{info.label}</p>
                      <p className="text-xs text-muted-foreground">{info.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            <p>By authorizing, you allow this application to access your data according to the permissions above.</p>
          </div>
        </CardContent>

        <CardFooter className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleDeny}
            disabled={status === "processing"}
          >
            Deny
          </Button>
          <Button
            className="flex-1"
            onClick={handleApprove}
            disabled={status === "processing"}
          >
            {status === "processing" ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Authorizing...
              </>
            ) : (
              "Authorize"
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
