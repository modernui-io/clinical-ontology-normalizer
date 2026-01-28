"use client";

import { useMemo } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { TrendingUp } from "lucide-react";

interface ConfidenceDataPoint {
  timestamp: string;
  confidence: number;
  queryText?: string;
  queryId?: string;
}

interface ConfidenceTrendProps {
  data: ConfidenceDataPoint[];
  patientId?: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: ConfidenceDataPoint }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  return (
    <div className="rounded-lg border bg-background p-2 shadow-md text-xs">
      <div className="font-medium">{Math.round(point.confidence * 100)}% confidence</div>
      {point.queryText && (
        <div className="text-muted-foreground mt-1 max-w-[200px] truncate">
          {point.queryText}
        </div>
      )}
      <div className="text-muted-foreground mt-1">
        {new Date(point.timestamp).toLocaleString()}
      </div>
    </div>
  );
}

export function ConfidenceTrend({ data, patientId }: ConfidenceTrendProps) {
  const chartData = useMemo(() => {
    return data.map((d, idx) => ({
      ...d,
      index: idx + 1,
      pct: Math.round(d.confidence * 100),
      label: new Date(d.timestamp).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
    }));
  }, [data]);

  const avgConfidence = useMemo(() => {
    if (data.length === 0) return 0;
    return data.reduce((sum, d) => sum + d.confidence, 0) / data.length;
  }, [data]);

  if (data.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-500" />
          Confidence Trend
          {patientId && (
            <span className="text-xs text-muted-foreground font-normal">
              ({data.length} queries)
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-3 px-4">
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10 }}
              className="text-muted-foreground"
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10 }}
              className="text-muted-foreground"
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={Math.round(avgConfidence * 100)}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="5 5"
              strokeOpacity={0.5}
            />
            <Line
              type="monotone"
              dataKey="pct"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={{ r: 3, fill: "hsl(var(--primary))" }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
