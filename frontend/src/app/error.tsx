"use client";

import { useEffect } from "react";
import { ErrorDisplay } from "@/components/ErrorBoundary";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Error Page
 * Handles both client and server errors with a user-friendly display
 * This is automatically rendered when an error occurs in the app
 */
export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log the error to console in development
    console.error("Application error:", error);

    // In production, you would send this to your error tracking service
    // Example: sendToErrorTracking(error);
  }, [error]);

  const handleRetry = () => {
    // Reset the error boundary to try re-rendering the segment
    reset();
  };

  const handleNavigateHome = () => {
    window.location.href = "/";
  };

  const handleReportError = () => {
    // Mock error reporting
    const errorReport = {
      message: error.message,
      stack: error.stack,
      digest: error.digest,
      timestamp: new Date().toISOString(),
      url: typeof window !== "undefined" ? window.location.href : "",
    };

    console.log("Error report:", errorReport);
    alert("Error report submitted. Thank you for helping us improve!");
  };

  // Determine if we should show error details
  const showDetails = process.env.NODE_ENV === "development";

  // Create a more user-friendly error message for common errors
  let errorTitle = "Something went wrong";
  let errorMessage = "We apologize for the inconvenience. An unexpected error has occurred.";

  // Customize message based on error type
  if (error.message?.includes("fetch")) {
    errorTitle = "Connection Error";
    errorMessage = "Unable to connect to the server. Please check your internet connection and try again.";
  } else if (error.message?.includes("timeout")) {
    errorTitle = "Request Timeout";
    errorMessage = "The request took too long to complete. Please try again.";
  } else if (error.message?.includes("401") || error.message?.includes("unauthorized")) {
    errorTitle = "Authentication Error";
    errorMessage = "Your session may have expired. Please sign in again.";
  } else if (error.message?.includes("403") || error.message?.includes("forbidden")) {
    errorTitle = "Access Denied";
    errorMessage = "You don't have permission to access this resource.";
  } else if (error.message?.includes("404") || error.message?.includes("not found")) {
    errorTitle = "Not Found";
    errorMessage = "The requested resource could not be found.";
  } else if (error.message?.includes("500") || error.message?.includes("server error")) {
    errorTitle = "Server Error";
    errorMessage = "The server encountered an error. Our team has been notified.";
  }

  return (
    <ErrorDisplay
      error={error}
      onRetry={handleRetry}
      onNavigateHome={handleNavigateHome}
      onReportError={handleReportError}
      showDetails={showDetails}
      errorTitle={errorTitle}
      errorMessage={errorMessage}
      fullPage={true}
    />
  );
}
