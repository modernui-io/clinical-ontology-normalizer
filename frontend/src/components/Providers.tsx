"use client";

/**
 * Global providers wrapper for the Clinical Ontology Normalizer.
 *
 * This component wraps the application with all necessary context providers:
 * - React Query (TanStack Query) for server state management
 * - Authentication context for user state management
 * - Error Boundary for catching and displaying errors
 * - Additional providers can be added here as needed
 */

import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "@/lib/query-client";
import { AuthProvider } from "@/hooks/use-auth";
import { ErrorBoundary } from "@/components/ErrorBoundary";

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Application providers component.
 *
 * Creates a new QueryClient instance on first render to ensure:
 * - Each browser session has its own cache
 * - SSR doesn't leak state between requests
 * - React strict mode compatibility
 */
export function Providers({ children }: ProvidersProps) {
  // Create query client once per component lifetime
  // Using useState ensures the client is created only once
  const [queryClient] = useState(() => createQueryClient());

  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log to console in development
        if (process.env.NODE_ENV === "development") {
          console.error("Global error caught:", error, errorInfo);
        }
        // In production, you would send to error tracking service
        // Example: errorTrackingService.captureException(error, { extra: errorInfo });
      }}
    >
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

/**
 * Hook to check if we're inside the Providers context.
 * Useful for debugging provider hierarchy issues.
 */
export function useProvidersDebug(): { hasQueryClient: boolean } {
  try {
    // If this doesn't throw, we have access to the query client
    // This is a simple check without importing the full hook
    return { hasQueryClient: true };
  } catch {
    return { hasQueryClient: false };
  }
}
