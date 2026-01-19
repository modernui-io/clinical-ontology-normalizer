import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Base Skeleton component with shimmer animation
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "relative overflow-hidden rounded-md bg-muted",
        "before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_2s_infinite]",
        "before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        className
      )}
      {...props}
    />
  )
}

/**
 * Skeleton for text content - renders multiple lines
 */
interface SkeletonTextProps extends React.HTMLAttributes<HTMLDivElement> {
  lines?: number
  lineHeight?: "sm" | "default" | "lg"
  lastLineWidth?: "full" | "3/4" | "1/2" | "1/4"
}

function SkeletonText({
  lines = 3,
  lineHeight = "default",
  lastLineWidth = "3/4",
  className,
  ...props
}: SkeletonTextProps) {
  const heights = {
    sm: "h-3",
    default: "h-4",
    lg: "h-5",
  }

  const widths = {
    full: "w-full",
    "3/4": "w-3/4",
    "1/2": "w-1/2",
    "1/4": "w-1/4",
  }

  return (
    <div
      data-slot="skeleton-text"
      className={cn("space-y-3", className)}
      {...props}
    >
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            heights[lineHeight],
            i === lines - 1 ? widths[lastLineWidth] : "w-full"
          )}
        />
      ))}
    </div>
  )
}

/**
 * Skeleton for card layouts
 */
interface SkeletonCardProps extends React.HTMLAttributes<HTMLDivElement> {
  showHeader?: boolean
  showFooter?: boolean
  contentLines?: number
}

function SkeletonCard({
  showHeader = true,
  showFooter = false,
  contentLines = 3,
  className,
  ...props
}: SkeletonCardProps) {
  return (
    <div
      data-slot="skeleton-card"
      className={cn(
        "rounded-xl border bg-card p-6 shadow-sm",
        className
      )}
      {...props}
    >
      {showHeader && (
        <div className="space-y-2 mb-6">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      )}
      <SkeletonText lines={contentLines} />
      {showFooter && (
        <div className="mt-6 flex gap-2">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-20" />
        </div>
      )}
    </div>
  )
}

/**
 * Skeleton for table layouts
 */
interface SkeletonTableProps extends React.HTMLAttributes<HTMLDivElement> {
  rows?: number
  columns?: number
  showHeader?: boolean
}

function SkeletonTable({
  rows = 5,
  columns = 4,
  showHeader = true,
  className,
  ...props
}: SkeletonTableProps) {
  return (
    <div
      data-slot="skeleton-table"
      className={cn("w-full", className)}
      {...props}
    >
      {/* Table Header */}
      {showHeader && (
        <div className="flex gap-4 border-b pb-3 mb-3">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton
              key={i}
              className={cn(
                "h-4",
                i === 0 ? "w-1/4" : "flex-1"
              )}
            />
          ))}
        </div>
      )}
      {/* Table Rows */}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="flex items-center gap-4 py-2">
            {Array.from({ length: columns }).map((_, colIndex) => (
              <Skeleton
                key={colIndex}
                className={cn(
                  "h-4",
                  colIndex === 0 ? "w-1/4" : "flex-1"
                )}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Skeleton for chart/visualization placeholders
 */
interface SkeletonChartProps extends React.HTMLAttributes<HTMLDivElement> {
  type?: "bar" | "line" | "pie" | "area"
  height?: number | string
}

function SkeletonChart({
  type = "bar",
  height = 200,
  className,
  ...props
}: SkeletonChartProps) {
  return (
    <div
      data-slot="skeleton-chart"
      className={cn("w-full", className)}
      style={{ height }}
      {...props}
    >
      {type === "bar" && (
        <div className="flex items-end justify-around h-full gap-2 pt-6 pb-6">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton
              key={i}
              className="flex-1 max-w-12"
              style={{
                height: `${30 + Math.random() * 60}%`,
              }}
            />
          ))}
        </div>
      )}
      {type === "line" && (
        <div className="h-full flex flex-col justify-center">
          <Skeleton className="h-full w-full rounded-lg" />
        </div>
      )}
      {type === "pie" && (
        <div className="h-full flex items-center justify-center">
          <Skeleton className="rounded-full" style={{ width: height, height }} />
        </div>
      )}
      {type === "area" && (
        <div className="h-full flex flex-col justify-end">
          <Skeleton className="h-3/4 w-full rounded-t-lg" />
        </div>
      )}
    </div>
  )
}

/**
 * Skeleton for avatar/profile images
 */
interface SkeletonAvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "default" | "lg" | "xl"
  shape?: "circle" | "rounded"
}

function SkeletonAvatar({
  size = "default",
  shape = "circle",
  className,
  ...props
}: SkeletonAvatarProps) {
  const sizes = {
    sm: "h-8 w-8",
    default: "h-10 w-10",
    lg: "h-12 w-12",
    xl: "h-16 w-16",
  }

  const shapes = {
    circle: "rounded-full",
    rounded: "rounded-md",
  }

  return (
    <Skeleton
      data-slot="skeleton-avatar"
      className={cn(sizes[size], shapes[shape], className)}
      {...props}
    />
  )
}

/**
 * Skeleton for list items with avatar and text
 */
interface SkeletonListItemProps extends React.HTMLAttributes<HTMLDivElement> {
  showAvatar?: boolean
  showSubtitle?: boolean
  showAction?: boolean
}

function SkeletonListItem({
  showAvatar = true,
  showSubtitle = true,
  showAction = false,
  className,
  ...props
}: SkeletonListItemProps) {
  return (
    <div
      data-slot="skeleton-list-item"
      className={cn("flex items-center gap-4 py-3", className)}
      {...props}
    >
      {showAvatar && <SkeletonAvatar size="default" />}
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-1/3" />
        {showSubtitle && <Skeleton className="h-3 w-1/2" />}
      </div>
      {showAction && <Skeleton className="h-8 w-8 rounded-md" />}
    </div>
  )
}

/**
 * Skeleton for form inputs
 */
interface SkeletonInputProps extends React.HTMLAttributes<HTMLDivElement> {
  showLabel?: boolean
}

function SkeletonInput({
  showLabel = true,
  className,
  ...props
}: SkeletonInputProps) {
  return (
    <div
      data-slot="skeleton-input"
      className={cn("space-y-2", className)}
      {...props}
    >
      {showLabel && <Skeleton className="h-4 w-24" />}
      <Skeleton className="h-9 w-full" />
    </div>
  )
}

/**
 * Skeleton for button
 */
interface SkeletonButtonProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "default" | "lg"
}

function SkeletonButton({
  size = "default",
  className,
  ...props
}: SkeletonButtonProps) {
  const sizes = {
    sm: "h-8 w-20",
    default: "h-9 w-24",
    lg: "h-10 w-28",
  }

  return (
    <Skeleton
      data-slot="skeleton-button"
      className={cn(sizes[size], "rounded-md", className)}
      {...props}
    />
  )
}

/**
 * Full page skeleton layout
 */
interface SkeletonPageProps extends React.HTMLAttributes<HTMLDivElement> {
  showHeader?: boolean
  showSidebar?: boolean
}

function SkeletonPage({
  showHeader = true,
  showSidebar = false,
  className,
  ...props
}: SkeletonPageProps) {
  return (
    <div
      data-slot="skeleton-page"
      className={cn("p-6 space-y-6", className)}
      {...props}
    >
      {/* Page Header */}
      {showHeader && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-1/4" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      )}

      {/* Content Grid */}
      <div className={cn("grid gap-6", showSidebar ? "lg:grid-cols-4" : "")}>
        {showSidebar && (
          <div className="space-y-4">
            <SkeletonCard contentLines={2} />
            <SkeletonCard showHeader={false} contentLines={4} />
          </div>
        )}
        <div className={cn(showSidebar ? "lg:col-span-3" : "", "space-y-6")}>
          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} contentLines={1} showHeader showFooter={false} />
            ))}
          </div>

          {/* Main Content */}
          <SkeletonCard contentLines={5} showHeader showFooter />
        </div>
      </div>
    </div>
  )
}

export {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonTable,
  SkeletonChart,
  SkeletonAvatar,
  SkeletonListItem,
  SkeletonInput,
  SkeletonButton,
  SkeletonPage,
}
