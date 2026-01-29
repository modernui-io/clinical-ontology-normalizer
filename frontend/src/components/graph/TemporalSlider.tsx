"use client";

import { useState, useCallback, useMemo } from "react";
import { format, parseISO, isValid } from "date-fns";

interface TemporalSliderProps {
  /** All event dates from edges */
  eventDates: (string | null)[];
  /** Current date range filter */
  dateRange: [Date | null, Date | null];
  /** Callback when date range changes */
  onDateRangeChange: (range: [Date | null, Date | null]) => void;
  /** Whether temporal filter is enabled */
  enabled: boolean;
  /** Toggle temporal filter */
  onToggle: (enabled: boolean) => void;
  /** Temporality filter (current/past/future) */
  temporalityFilter: string | null;
  /** Callback for temporality filter change */
  onTemporalityChange: (temporality: string | null) => void;
}

export function TemporalSlider({
  eventDates,
  dateRange,
  onDateRangeChange,
  enabled,
  onToggle,
  temporalityFilter,
  onTemporalityChange,
}: TemporalSliderProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Parse and sort valid dates
  const validDates = useMemo(() => {
    return eventDates
      .filter((d): d is string => d !== null)
      .map((d) => {
        try {
          const parsed = parseISO(d);
          return isValid(parsed) ? parsed : null;
        } catch {
          return null;
        }
      })
      .filter((d): d is Date => d !== null)
      .sort((a, b) => a.getTime() - b.getTime());
  }, [eventDates]);

  const minDate = validDates.length > 0 ? validDates[0] : new Date();
  const maxDate = validDates.length > 0 ? validDates[validDates.length - 1] : new Date();

  // Calculate timeline markers
  const timelineMarkers = useMemo(() => {
    if (validDates.length === 0) return [];

    const range = maxDate.getTime() - minDate.getTime();
    if (range === 0) return [{ position: 50, date: minDate, count: validDates.length }];

    // Group dates by month for markers
    const monthGroups = new Map<string, Date[]>();
    validDates.forEach((d) => {
      const key = format(d, "yyyy-MM");
      if (!monthGroups.has(key)) {
        monthGroups.set(key, []);
      }
      monthGroups.get(key)!.push(d);
    });

    const markers: { position: number; date: Date; count: number }[] = [];
    monthGroups.forEach((dates, key) => {
      const representativeDate = dates[0];
      const position = ((representativeDate.getTime() - minDate.getTime()) / range) * 100;
      markers.push({ position, date: representativeDate, count: dates.length });
    });

    return markers.slice(0, 12); // Limit to 12 markers
  }, [validDates, minDate, maxDate]);

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>, isStart: boolean) => {
      const value = parseInt(e.target.value);
      const range = maxDate.getTime() - minDate.getTime();
      const newDate = new Date(minDate.getTime() + (value / 100) * range);

      if (isStart) {
        onDateRangeChange([newDate, dateRange[1]]);
      } else {
        onDateRangeChange([dateRange[0], newDate]);
      }
    },
    [minDate, maxDate, dateRange, onDateRangeChange]
  );

  const sliderStartValue = useMemo(() => {
    if (!dateRange[0] || validDates.length === 0) return 0;
    const range = maxDate.getTime() - minDate.getTime();
    if (range === 0) return 0;
    return Math.max(0, Math.min(100, ((dateRange[0].getTime() - minDate.getTime()) / range) * 100));
  }, [dateRange, minDate, maxDate, validDates.length]);

  const sliderEndValue = useMemo(() => {
    if (!dateRange[1] || validDates.length === 0) return 100;
    const range = maxDate.getTime() - minDate.getTime();
    if (range === 0) return 100;
    return Math.max(0, Math.min(100, ((dateRange[1].getTime() - minDate.getTime()) / range) * 100));
  }, [dateRange, minDate, maxDate, validDates.length]);

  const resetDateRange = useCallback(() => {
    onDateRangeChange([null, null]);
  }, [onDateRangeChange]);

  if (validDates.length === 0) {
    return (
      <div className="bg-slate-800/60 rounded-lg p-3 backdrop-blur-sm border border-slate-700/50">
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>No temporal data available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/60 rounded-lg p-3 backdrop-blur-sm border border-slate-700/50">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-slate-300 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-medium">Temporal Filter</span>
          <svg
            className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <label className="flex items-center gap-2 cursor-pointer">
          <span className="text-xs text-slate-400">{enabled ? "On" : "Off"}</span>
          <div className="relative">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600 peer-checked:after:bg-white"></div>
          </div>
        </label>
      </div>

      {isExpanded && (
        <div className="space-y-3">
          {/* Temporality Filter Chips */}
          <div className="flex gap-2">
            {["current", "past", "future"].map((temp) => (
              <button
                key={temp}
                onClick={() => onTemporalityChange(temporalityFilter === temp ? null : temp)}
                className={`px-3 py-1 text-xs rounded-full transition-all ${
                  temporalityFilter === temp
                    ? temp === "current"
                      ? "bg-green-500/20 text-green-400 border border-green-500/40"
                      : temp === "past"
                      ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                      : "bg-blue-500/20 text-blue-400 border border-blue-500/40"
                    : "bg-slate-700/50 text-slate-400 border border-slate-600/50 hover:bg-slate-600/50"
                }`}
              >
                {temp.charAt(0).toUpperCase() + temp.slice(1)}
              </button>
            ))}
          </div>

          {/* Timeline Visualization */}
          <div className="relative h-8 bg-slate-900/50 rounded overflow-hidden">
            {/* Event density markers */}
            {timelineMarkers.map((marker, i) => (
              <div
                key={i}
                className="absolute bottom-0 w-1 bg-cyan-400/60 rounded-t"
                style={{
                  left: `${marker.position}%`,
                  height: `${Math.min(100, 20 + marker.count * 10)}%`,
                }}
                title={`${format(marker.date, "MMM yyyy")}: ${marker.count} events`}
              />
            ))}

            {/* Selected range overlay */}
            {enabled && (
              <div
                className="absolute top-0 bottom-0 bg-cyan-400/20 border-x border-cyan-400/40"
                style={{
                  left: `${sliderStartValue}%`,
                  width: `${sliderEndValue - sliderStartValue}%`,
                }}
              />
            )}
          </div>

          {/* Date Range Sliders */}
          {enabled && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-12">From:</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={sliderStartValue}
                  onChange={(e) => handleSliderChange(e, true)}
                  className="flex-1 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                />
                <span className="text-xs text-slate-300 w-24 text-right">
                  {dateRange[0] ? format(dateRange[0], "MMM d, yyyy") : format(minDate, "MMM d, yyyy")}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-12">To:</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={sliderEndValue}
                  onChange={(e) => handleSliderChange(e, false)}
                  className="flex-1 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                />
                <span className="text-xs text-slate-300 w-24 text-right">
                  {dateRange[1] ? format(dateRange[1], "MMM d, yyyy") : format(maxDate, "MMM d, yyyy")}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-500">
                  {validDates.length} events from {format(minDate, "MMM yyyy")} to {format(maxDate, "MMM yyyy")}
                </span>
                <button
                  onClick={resetDateRange}
                  className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  Reset
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
