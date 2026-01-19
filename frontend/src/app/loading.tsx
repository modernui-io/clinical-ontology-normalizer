import { SkeletonPage } from "@/components/ui/skeleton";
import { Loader2 } from "lucide-react";

/**
 * Global Loading State
 * Displayed automatically by Next.js during route transitions
 * and server component loading
 */
export default function Loading() {
  return (
    <div className="relative min-h-[calc(100vh-4rem)]">
      {/* Loading overlay with spinner */}
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm z-10">
        <div className="flex flex-col items-center gap-4">
          {/* Animated spinner */}
          <div className="relative">
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
            {/* Pulse effect behind spinner */}
            <div className="absolute inset-0 h-12 w-12 rounded-full bg-primary/20 animate-pulse" />
          </div>

          {/* Loading message */}
          <div className="text-center space-y-1">
            <p className="text-lg font-medium text-foreground">Loading...</p>
            <p className="text-sm text-muted-foreground">
              Please wait while we fetch your data
            </p>
          </div>
        </div>
      </div>

      {/* Background skeleton for visual context */}
      <div className="opacity-30 pointer-events-none" aria-hidden="true">
        <SkeletonPage showHeader showSidebar={false} />
      </div>
    </div>
  );
}
