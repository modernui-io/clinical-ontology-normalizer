"use client";

import * as React from "react";
import { AlertTriangle, Home, RefreshCw, Bug, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /**
   * Custom fallback component to render when an error occurs
   */
  fallback?: React.ReactNode;
  /**
   * Callback when an error is caught
   */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  /**
   * Custom class name for the error display
   */
  className?: string;
  /**
   * Show error details (stack trace) - defaults to development mode
   */
  showDetails?: boolean;
  /**
   * Custom error title
   */
  errorTitle?: string;
  /**
   * Custom error message
   */
  errorMessage?: string;
}

/**
 * Global Error Boundary component that catches React errors
 * and displays a friendly error message with options to retry or navigate home
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });

    // Call the onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log error to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleNavigateHome = () => {
    window.location.href = "/";
  };

  handleReportError = () => {
    // Mock error reporting - in production, this would send to an error tracking service
    const { error, errorInfo } = this.state;
    const errorReport = {
      message: error?.message,
      stack: error?.stack,
      componentStack: errorInfo?.componentStack,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    };

    console.log("Error report would be sent:", errorReport);

    // Show a mock success message
    alert("Error report submitted. Thank you for helping us improve!");
  };

  render() {
    const { hasError, error, errorInfo } = this.state;
    const {
      children,
      fallback,
      className,
      showDetails = process.env.NODE_ENV === "development",
      errorTitle = "Something went wrong",
      errorMessage = "We apologize for the inconvenience. An unexpected error has occurred.",
    } = this.props;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      // Default error display
      return (
        <ErrorDisplay
          error={error}
          errorInfo={errorInfo}
          onRetry={this.handleRetry}
          onNavigateHome={this.handleNavigateHome}
          onReportError={this.handleReportError}
          showDetails={showDetails}
          className={className}
          errorTitle={errorTitle}
          errorMessage={errorMessage}
        />
      );
    }

    return children;
  }
}

/**
 * Error display component used by ErrorBoundary
 * Can also be used standalone for displaying errors
 */
interface ErrorDisplayProps {
  error?: Error | null;
  errorInfo?: React.ErrorInfo | null;
  onRetry?: () => void;
  onNavigateHome?: () => void;
  onReportError?: () => void;
  showDetails?: boolean;
  className?: string;
  errorTitle?: string;
  errorMessage?: string;
  /**
   * Whether to show as full page or inline
   */
  fullPage?: boolean;
}

export function ErrorDisplay({
  error,
  errorInfo,
  onRetry,
  onNavigateHome,
  onReportError,
  showDetails = false,
  className,
  errorTitle = "Something went wrong",
  errorMessage = "We apologize for the inconvenience. An unexpected error has occurred.",
  fullPage = true,
}: ErrorDisplayProps) {
  const [isDetailsExpanded, setIsDetailsExpanded] = React.useState(false);

  const content = (
    <Card className={cn("w-full max-w-lg", className)} role="alert" aria-live="polite">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10" aria-hidden="true">
          <AlertTriangle className="h-8 w-8 text-destructive" />
        </div>
        <CardTitle className="text-xl">{errorTitle}</CardTitle>
        <CardDescription className="text-base">{errorMessage}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Quick actions */}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center" role="group" aria-label="Recovery options">
          {onRetry && (
            <Button onClick={onRetry} className="gap-2">
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try Again
            </Button>
          )}
          {onNavigateHome && (
            <Button variant="outline" onClick={onNavigateHome} className="gap-2">
              <Home className="h-4 w-4" aria-hidden="true" />
              Go Home
            </Button>
          )}
          {onReportError && (
            <Button variant="ghost" onClick={onReportError} className="gap-2">
              <Bug className="h-4 w-4" aria-hidden="true" />
              Report Error
            </Button>
          )}
        </div>

        {/* Error details (dev mode) */}
        {showDetails && error && (
          <div className="mt-6 border-t pt-4">
            <button
              type="button"
              onClick={() => setIsDetailsExpanded(!isDetailsExpanded)}
              className="flex w-full items-center justify-between text-sm text-muted-foreground hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-sm"
              aria-expanded={isDetailsExpanded}
              aria-controls="error-details-content"
            >
              <span className="font-medium">Error Details</span>
              {isDetailsExpanded ? (
                <ChevronUp className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              )}
            </button>

            {isDetailsExpanded && (
              <div id="error-details-content" className="mt-4 space-y-4" role="region" aria-label="Error details">
                {/* Error message */}
                <div>
                  <p id="error-message-label" className="text-xs font-medium text-muted-foreground mb-1">
                    Error Message
                  </p>
                  <pre
                    className="rounded-md bg-muted p-3 text-xs overflow-auto max-h-24"
                    aria-labelledby="error-message-label"
                    tabIndex={0}
                  >
                    {error.message}
                  </pre>
                </div>

                {/* Stack trace */}
                {error.stack && (
                  <div>
                    <p id="stack-trace-label" className="text-xs font-medium text-muted-foreground mb-1">
                      Stack Trace
                    </p>
                    <pre
                      className="rounded-md bg-muted p-3 text-xs overflow-auto max-h-48 whitespace-pre-wrap break-words"
                      aria-labelledby="stack-trace-label"
                      tabIndex={0}
                    >
                      {error.stack}
                    </pre>
                  </div>
                )}

                {/* Component stack */}
                {errorInfo?.componentStack && (
                  <div>
                    <p id="component-stack-label" className="text-xs font-medium text-muted-foreground mb-1">
                      Component Stack
                    </p>
                    <pre
                      className="rounded-md bg-muted p-3 text-xs overflow-auto max-h-48 whitespace-pre-wrap break-words"
                      aria-labelledby="component-stack-label"
                      tabIndex={0}
                    >
                      {errorInfo.componentStack}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter className="justify-center text-center">
        <p className="text-xs text-muted-foreground">
          If this problem persists, please contact support.
        </p>
      </CardFooter>
    </Card>
  );

  if (fullPage) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center p-6">
        {content}
      </div>
    );
  }

  return content;
}

/**
 * Hook to programmatically trigger error boundary
 * Useful for async errors that aren't caught by React's error boundary
 */
export function useErrorHandler(): (error: Error) => void {
  const [, setError] = React.useState<Error | null>(null);

  return React.useCallback((error: Error) => {
    setError(() => {
      throw error;
    });
  }, []);
}

/**
 * Higher-order component to wrap a component with an error boundary
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, "children">
): React.FC<P> {
  const WrappedComponent: React.FC<P> = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${
    Component.displayName || Component.name || "Component"
  })`;

  return WrappedComponent;
}

export default ErrorBoundary;
