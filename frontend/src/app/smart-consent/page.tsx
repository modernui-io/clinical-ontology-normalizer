"use client";

/**
 * SMART on FHIR Consent Page
 *
 * Displays authorization consent screen when a SMART app requests access.
 * Shows app details, requested scopes, and patient context.
 * User can approve or deny the authorization request.
 */

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, Shield, User, FileText, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Scope descriptions for user-friendly display
const SCOPE_DESCRIPTIONS: Record<string, { label: string; description: string; icon: string }> = {
  "openid": { label: "OpenID Connect", description: "Verify your identity", icon: "user" },
  "fhirUser": { label: "FHIR User", description: "Access your user profile", icon: "user" },
  "launch": { label: "Launch Context", description: "Receive launch context from EHR", icon: "rocket" },
  "launch/patient": { label: "Patient Context", description: "Access current patient context", icon: "user" },
  "launch/encounter": { label: "Encounter Context", description: "Access current encounter context", icon: "calendar" },
  "patient/*.read": { label: "Read Patient Data", description: "Read all patient resources", icon: "file" },
  "patient/*.write": { label: "Write Patient Data", description: "Create and update patient resources", icon: "edit" },
  "user/*.read": { label: "Read User Data", description: "Read resources accessible to user", icon: "file" },
  "user/*.write": { label: "Write User Data", description: "Create and update user-accessible resources", icon: "edit" },
  "offline_access": { label: "Offline Access", description: "Access data when you're not logged in", icon: "refresh" },
};

function getIconForScope(iconType: string) {
  switch (iconType) {
    case "user":
      return <User className="h-4 w-4" />;
    case "file":
      return <FileText className="h-4 w-4" />;
    default:
      return <Shield className="h-4 w-4" />;
  }
}

function ConsentContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Extract parameters from URL
  const clientId = searchParams.get("client_id") || "";
  const clientName = searchParams.get("client_name") || "Unknown App";
  const redirectUri = searchParams.get("redirect_uri") || "";
  const scope = searchParams.get("scope") || "";
  const state = searchParams.get("state") || "";
  const patientId = searchParams.get("patient_id") || "";
  const encounterId = searchParams.get("encounter_id") || "";
  const codeChallenge = searchParams.get("code_challenge") || "";
  const codeChallengeMethod = searchParams.get("code_challenge_method") || "S256";
  const logoUri = searchParams.get("logo_uri") || "";

  const scopes = scope.split(" ").filter(Boolean);

  const handleApprove = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // POST to authorize endpoint to generate auth code
      const response = await fetch(`${API_BASE_URL}/api/v1/smart-server/authorize`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: clientId,
          redirect_uri: redirectUri,
          scope,
          state,
          code_challenge: codeChallenge,
          code_challenge_method: codeChallengeMethod,
          patient_id: patientId,
          encounter_id: encounterId,
          user_approved: "true",
        }),
      });

      if (!response.ok) {
        // If redirect, follow it
        if (response.status === 302 || response.redirected) {
          const redirectUrl = response.headers.get("Location") || response.url;
          window.location.href = redirectUrl;
          return;
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Authorization failed");
      }

      // The backend should redirect, but if we get JSON, extract the redirect URL
      const data = await response.json();
      if (data.redirect_uri) {
        window.location.href = data.redirect_uri;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authorization failed");
      setIsLoading(false);
    }
  };

  const handleDeny = () => {
    // Redirect back to app with error
    const errorParams = new URLSearchParams({
      error: "access_denied",
      error_description: "User denied the authorization request",
      state,
    });
    window.location.href = `${redirectUri}?${errorParams.toString()}`;
  };

  if (!clientId || !redirectUri) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <AlertTriangle className="h-5 w-5" />
              Invalid Request
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Missing required authorization parameters.
            </p>
          </CardContent>
          <CardFooter>
            <Button onClick={() => router.push("/")} variant="outline">
              Return Home
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          {logoUri && (
            <img
              src={logoUri}
              alt={clientName}
              className="h-16 w-16 mx-auto mb-4 rounded-lg"
            />
          )}
          <CardTitle className="text-2xl">{clientName}</CardTitle>
          <CardDescription>
            is requesting access to your health data
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Patient Context */}
          {patientId && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
              <div className="flex items-center gap-2 text-blue-400 mb-2">
                <User className="h-4 w-4" />
                <span className="font-medium">Patient Context</span>
              </div>
              <p className="text-sm text-muted-foreground">
                This app will have access to data for patient: {patientId}
              </p>
            </div>
          )}

          {/* Requested Permissions */}
          <div>
            <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Shield className="h-4 w-4" />
              Requested Permissions
            </h3>
            <div className="space-y-2">
              {scopes.map((scopeItem) => {
                const scopeInfo = SCOPE_DESCRIPTIONS[scopeItem] || {
                  label: scopeItem,
                  description: `Access to ${scopeItem}`,
                  icon: "shield",
                };
                return (
                  <div
                    key={scopeItem}
                    className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg"
                  >
                    <div className="mt-0.5 text-muted-foreground">
                      {getIconForScope(scopeInfo.icon)}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{scopeInfo.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {scopeInfo.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <Separator />

          {/* Security Notice */}
          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              By clicking &quot;Approve&quot;, you agree to share the above information
              with <strong>{clientName}</strong>.
            </p>
            <p>
              You can revoke access at any time from your account settings.
            </p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400 text-sm">
              {error}
            </div>
          )}
        </CardContent>

        <CardFooter className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleDeny}
            disabled={isLoading}
          >
            <XCircle className="h-4 w-4 mr-2" />
            Deny
          </Button>
          <Button
            className="flex-1"
            onClick={handleApprove}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <CheckCircle className="h-4 w-4 mr-2" />
            )}
            Approve
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

export default function SMARTConsentPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-900">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <ConsentContent />
    </Suspense>
  );
}
