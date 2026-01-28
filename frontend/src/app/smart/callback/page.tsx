"use client";

/**
 * SMART on FHIR OAuth2 Callback Handler
 *
 * Handles the OAuth2 callback by:
 * 1. Extracting the authorization code from query params
 * 2. Verifying the state parameter
 * 3. Exchanging the code for tokens using PKCE
 * 4. Storing tokens and redirecting to the app
 */

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, AlertCircle, CheckCircle } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  scope: string;
  patient?: string;
  encounter?: string;
}

export default function SMARTCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [tokenData, setTokenData] = useState<TokenResponse | null>(null);

  useEffect(() => {
    async function handleCallback() {
      try {
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const errorParam = searchParams.get("error");
        const errorDescription = searchParams.get("error_description");

        // Check for OAuth error response
        if (errorParam) {
          throw new Error(errorDescription || errorParam);
        }

        if (!code) {
          throw new Error("Missing authorization code");
        }

        // Verify state
        const storedState = sessionStorage.getItem("smart_state");
        if (state !== storedState) {
          throw new Error("State mismatch - possible CSRF attack");
        }

        // Get stored code verifier
        const codeVerifier = sessionStorage.getItem("smart_code_verifier");
        if (!codeVerifier) {
          throw new Error("Missing code verifier - session expired");
        }

        // Exchange code for tokens
        const tokenResponse = await fetch(`${API_BASE_URL}/api/v1/smart-server/token`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "authorization_code",
            code,
            redirect_uri: `${window.location.origin}/smart/callback`,
            client_id: "test-smart-app",
            code_verifier: codeVerifier,
          }),
        });

        if (!tokenResponse.ok) {
          const errorData = await tokenResponse.json().catch(() => ({}));
          throw new Error(errorData.error_description || errorData.error || "Token exchange failed");
        }

        const tokens: TokenResponse = await tokenResponse.json();

        // Store tokens
        sessionStorage.setItem("smart_access_token", tokens.access_token);
        if (tokens.refresh_token) {
          sessionStorage.setItem("smart_refresh_token", tokens.refresh_token);
        }
        if (tokens.patient) {
          sessionStorage.setItem("smart_patient_id", tokens.patient);
        }
        if (tokens.encounter) {
          sessionStorage.setItem("smart_encounter_id", tokens.encounter);
        }

        // Clean up
        sessionStorage.removeItem("smart_code_verifier");
        sessionStorage.removeItem("smart_state");

        setTokenData(tokens);
        setStatus("success");

        // Redirect to patient view if we have patient context
        if (tokens.patient) {
          setTimeout(() => {
            router.push(`/patients/${tokens.patient}/summary`);
          }, 2000);
        }
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Callback failed");
      }
    }

    handleCallback();
  }, [searchParams, router]);

  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <AlertCircle className="h-5 w-5" />
              Authorization Failed
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">{error}</p>
            <Button onClick={() => router.push("/login")} variant="outline">
              Return to Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "success" && tokenData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-500">
              <CheckCircle className="h-5 w-5" />
              Authorization Successful
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-sm space-y-2">
              <p>
                <span className="text-muted-foreground">Scope:</span>{" "}
                {tokenData.scope}
              </p>
              {tokenData.patient && (
                <p>
                  <span className="text-muted-foreground">Patient:</span>{" "}
                  {tokenData.patient}
                </p>
              )}
              {tokenData.encounter && (
                <p>
                  <span className="text-muted-foreground">Encounter:</span>{" "}
                  {tokenData.encounter}
                </p>
              )}
            </div>
            <p className="text-muted-foreground text-sm">
              Redirecting to patient view...
            </p>
            <Loader2 className="h-5 w-5 animate-spin mx-auto" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Processing Authorization</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Exchanging authorization code...</p>
        </CardContent>
      </Card>
    </div>
  );
}
