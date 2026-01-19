"use client";

import * as React from "react";
import { Search, X, Loader2, Command } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Custom hook for debouncing values
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

interface SearchWithDebounceProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "size" | "onSubmit"> {
  /**
   * Callback when the debounced value changes
   */
  onSearch: (value: string) => void;
  /**
   * Debounce delay in milliseconds
   * @default 300
   */
  debounceMs?: number;
  /**
   * Show loading indicator
   */
  isLoading?: boolean;
  /**
   * Custom class name for the container
   */
  containerClassName?: string;
  /**
   * Show keyboard shortcut hint
   * @default true
   */
  showShortcut?: boolean;
  /**
   * Custom placeholder text
   * @default "Search..."
   */
  placeholder?: string;
  /**
   * Initial value
   */
  defaultValue?: string;
  /**
   * Controlled value
   */
  value?: string;
  /**
   * Callback when input value changes (immediate, not debounced)
   */
  onChange?: (value: string) => void;
  /**
   * Whether to focus on mount
   * @default false
   */
  autoFocus?: boolean;
  /**
   * Size variant
   * @default "default"
   */
  size?: "sm" | "default" | "lg";
  /**
   * Callback when search is cleared
   */
  onClear?: () => void;
  /**
   * Callback when Enter is pressed
   */
  onSubmit?: (value: string) => void;
}

/**
 * Live search component with debounced input
 * Features:
 * - Debounced search (300ms default)
 * - Loading indicator while searching
 * - Clear button
 * - Search icon
 * - Keyboard shortcuts (Cmd+K / Ctrl+K to focus)
 */
export function SearchWithDebounce({
  onSearch,
  debounceMs = 300,
  isLoading = false,
  containerClassName,
  showShortcut = true,
  placeholder = "Search...",
  defaultValue = "",
  value: controlledValue,
  onChange,
  autoFocus = false,
  size = "default",
  onClear,
  onSubmit,
  className,
  disabled,
  ...inputProps
}: SearchWithDebounceProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [internalValue, setInternalValue] = React.useState(defaultValue);

  // Use controlled value if provided, otherwise use internal state
  const value = controlledValue !== undefined ? controlledValue : internalValue;

  // Debounce the search value
  const debouncedValue = useDebounce(value, debounceMs);

  // Track if the debounced value was triggered by user input
  const hasUserInput = React.useRef(false);

  // Call onSearch when debounced value changes
  React.useEffect(() => {
    if (hasUserInput.current) {
      onSearch(debouncedValue);
      hasUserInput.current = false;
    }
  }, [debouncedValue, onSearch]);

  // Handle keyboard shortcuts
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K (Mac) or Ctrl+K (Windows/Linux) to focus search
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }

      // Escape to blur and clear
      if (e.key === "Escape" && document.activeElement === inputRef.current) {
        inputRef.current?.blur();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto focus on mount
  React.useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
    }
  }, [autoFocus]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    hasUserInput.current = true;

    if (controlledValue === undefined) {
      setInternalValue(newValue);
    }

    onChange?.(newValue);
  };

  const handleClear = () => {
    hasUserInput.current = true;

    if (controlledValue === undefined) {
      setInternalValue("");
    }

    onChange?.("");
    onClear?.();
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && onSubmit) {
      onSubmit(value);
    }
  };

  // Size variants
  const sizeClasses = {
    sm: "h-8 text-sm",
    default: "h-9",
    lg: "h-10 text-base",
  };

  const iconSizes = {
    sm: "h-3.5 w-3.5",
    default: "h-4 w-4",
    lg: "h-5 w-5",
  };

  const paddingClasses = {
    sm: "pl-8 pr-8",
    default: "pl-9 pr-9",
    lg: "pl-10 pr-10",
  };

  return (
    <div className={cn("relative", containerClassName)}>
      {/* Search icon */}
      <div
        className={cn(
          "absolute left-0 top-0 flex items-center justify-center pointer-events-none text-muted-foreground",
          size === "sm" ? "h-8 w-8" : size === "lg" ? "h-10 w-10" : "h-9 w-9"
        )}
      >
        {isLoading ? (
          <Loader2 className={cn(iconSizes[size], "animate-spin")} />
        ) : (
          <Search className={iconSizes[size]} />
        )}
      </div>

      {/* Input */}
      <Input
        ref={inputRef}
        type="search"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          sizeClasses[size],
          paddingClasses[size],
          // Hide native search clear button
          "[&::-webkit-search-cancel-button]:hidden [&::-webkit-search-decoration]:hidden",
          className
        )}
        {...inputProps}
      />

      {/* Right side actions */}
      <div
        className={cn(
          "absolute right-0 top-0 flex items-center gap-1 pr-1",
          size === "sm" ? "h-8" : size === "lg" ? "h-10" : "h-9"
        )}
      >
        {/* Clear button - show when there's a value */}
        {value && !disabled && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={handleClear}
            className={cn(
              "text-muted-foreground hover:text-foreground",
              size === "sm" ? "h-6 w-6" : size === "lg" ? "h-8 w-8" : "h-7 w-7"
            )}
            aria-label="Clear search"
          >
            <X className={iconSizes[size]} />
          </Button>
        )}

        {/* Keyboard shortcut hint - show when empty and not focused */}
        {showShortcut && !value && !disabled && (
          <kbd
            className={cn(
              "hidden sm:inline-flex items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-muted-foreground",
              size === "sm" ? "h-5 text-[10px]" : size === "lg" ? "h-7 text-sm" : "h-6 text-xs"
            )}
          >
            <Command className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3")} />
            <span>K</span>
          </kbd>
        )}
      </div>
    </div>
  );
}

/**
 * Simplified hook for search with debounce
 * Returns [value, debouncedValue, setValue]
 */
export function useSearch(
  initialValue: string = "",
  debounceMs: number = 300
): [string, string, (value: string) => void] {
  const [value, setValue] = React.useState(initialValue);
  const debouncedValue = useDebounce(value, debounceMs);

  return [value, debouncedValue, setValue];
}

/**
 * Hook for search with callback
 * Automatically calls onSearch when debounced value changes
 */
export function useSearchWithCallback(
  onSearch: (value: string) => void,
  initialValue: string = "",
  debounceMs: number = 300
): [string, (value: string) => void, boolean] {
  const [value, debouncedValue, setValue] = useSearch(initialValue, debounceMs);
  const [isSearching, setIsSearching] = React.useState(false);

  // Track if searching
  React.useEffect(() => {
    setIsSearching(value !== debouncedValue);
  }, [value, debouncedValue]);

  // Call onSearch when debounced value changes
  React.useEffect(() => {
    onSearch(debouncedValue);
  }, [debouncedValue, onSearch]);

  return [value, setValue, isSearching];
}

export { useDebounce };
export default SearchWithDebounce;
