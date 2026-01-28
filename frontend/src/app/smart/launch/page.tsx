"use client";

/**
 * SMART on FHIR Launch Handler
 *
 * Handles incoming EHR launches by:
 * 1. Reading `iss` (FHIR server URL) and `launch` (context token) from query params
 * 2. Fetching the SMART configuration from the issuer
 * 3. Redirecting to the authorization endpoint with proper parameters
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, AlertCircle } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SMARTLaunchPage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function handleLaunch() {
      try {
        const iss = searchParams.get("iss");
        const launch = searchParams.get("launch");

        if (!iss) {
          throw new Error("Missing required 'iss' parameter");
        }

        // For standalone launch, we use our own server
        // For EHR launch, we'd fetch from the EHR's .well-known endpoint
        const configUrl = iss.includes("localhost")
          ? `${API_BASE_URL}/.well-known/smart-configuration`
          : `${iss}/.well-known/smart-configuration`;

        const configResponse = await fetch(configUrl);
        if (!configResponse.ok) {
          throw new Error("Failed to fetch SMART configuration");
        }

        const config = await configResponse.json();

        // Build authorization URL
        const authUrl = new URL(config.authorization_endpoint);
        authUrl.searchParams.set("response_type", "code");
        authUrl.searchParams.set("client_id", "test-smart-app"); // Use registered client
        authUrl.searchParams.set("redirect_uri", `${window.location.origin}/smart/callback`);
        authUrl.searchParams.set("scope", "openid fhirUser launch/patient patient/*.read");
        authUrl.searchParams.set("state", crypto.randomUUID());
        authUrl.searchParams.set("aud", iss);

        // Generate PKCE challenge
        const codeVerifier = generateCodeVerifier();
        const codeChallenge = await generateCodeChallenge(codeVerifier);
        authUrl.searchParams.set("code_challenge", codeChallenge);
        authUrl.searchParams.set("code_challenge_method", "S256");

        // Store code verifier for callback
        sessionStorage.setItem("smart_code_verifier", codeVerifier);
        sessionStorage.setItem("smart_state", authUrl.searchParams.get("state") || "");

        // Add launch token if present (EHR launch)
        if (launch) {
          authUrl.searchParams.set("launch", launch);
        }

        // Redirect to authorization
        window.location.href = authUrl.toString();
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Launch failed");
      }
    }

    handleLaunch();
  }, [searchParams]);

  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <AlertCircle className="h-5 w-5" />
              Launch Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>SMART Launch</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Initiating SMART on FHIR launch...</p>
        </CardContent>
      </Card>
    </div>
  );
}

// PKCE helpers
function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(hash));
}

function base64UrlEncode(buffer: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < buffer.length; i++) {
    binary += String.fromCharCode(buffer[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
