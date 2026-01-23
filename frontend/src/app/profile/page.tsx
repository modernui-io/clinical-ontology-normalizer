"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  User,
  Mail,
  Shield,
  Key,
  Clock,
  Activity,
  Settings,
  BarChart3,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

interface APIUsageStats {
  total_requests: number;
  requests_today: number;
  requests_this_week: number;
  top_endpoints: { endpoint: string; count: number }[];
}

interface ActivityEntry {
  id: string;
  action: string;
  resource: string;
  timestamp: string;
}

export default function ProfilePage() {
  const { user, isAuthenticated } = useAuth();
  const [apiUsage, setApiUsage] = useState<APIUsageStats | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [loadingUsage, setLoadingUsage] = useState(true);

  useEffect(() => {
    // Simulate loading API usage stats
    const timer = setTimeout(() => {
      setApiUsage({
        total_requests: 12847,
        requests_today: 156,
        requests_this_week: 892,
        top_endpoints: [
          { endpoint: "POST /icd10-suggestions/suggest", count: 3420 },
          { endpoint: "POST /hcc-analysis/analyze", count: 2815 },
          { endpoint: "POST /drug-safety/check", count: 2103 },
          { endpoint: "GET /search/concepts", count: 1892 },
          { endpoint: "POST /differential-diagnosis/generate", count: 1456 },
        ],
      });
      setActivity([
        { id: "1", action: "ICD-10 Code Lookup", resource: "E11.9", timestamp: "2 min ago" },
        { id: "2", action: "Drug Safety Check", resource: "warfarin", timestamp: "15 min ago" },
        { id: "3", action: "HCC Analysis", resource: "Patient P-12345", timestamp: "1 hour ago" },
        { id: "4", action: "Vocabulary Mapping", resource: "J18.9 → SNOMED", timestamp: "2 hours ago" },
        { id: "5", action: "Differential Dx", resource: "chest pain", timestamp: "3 hours ago" },
        { id: "6", action: "CPT Suggestion", resource: "E/M Level 4", timestamp: "5 hours ago" },
      ]);
      setLoadingUsage(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const displayUser = user || {
    id: "user-001",
    email: "user@example.com",
    name: "Clinical User",
    roles: ["clinician", "coder"],
    permissions: ["read:concepts", "write:mappings", "read:audit", "execute:clinical"],
  };

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">User Profile</h1>
        <Link href="/settings">
          <Button variant="outline" size="sm">
            <Settings className="h-4 w-4 mr-1" /> Edit Settings
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* User Info Card */}
        <Card className="lg:col-span-1">
          <CardHeader className="text-center pb-3">
            <div className="mx-auto w-20 h-20 rounded-full bg-muted flex items-center justify-center mb-3">
              <User className="h-10 w-10 text-muted-foreground" />
            </div>
            <CardTitle>{displayUser.name}</CardTitle>
            <CardDescription className="flex items-center justify-center gap-1">
              <Mail className="h-3 w-3" /> {displayUser.email}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <Shield className="h-3 w-3" /> Roles
              </p>
              <div className="flex flex-wrap gap-1">
                {displayUser.roles.map((role) => (
                  <Badge key={role} variant="default" className="text-xs">
                    {role}
                  </Badge>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <Key className="h-3 w-3" /> Permissions
              </p>
              <div className="flex flex-wrap gap-1">
                {displayUser.permissions.map((perm) => (
                  <Badge key={perm} variant="outline" className="text-xs">
                    {perm}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* API Usage and Activity */}
        <div className="lg:col-span-2 space-y-6">
          {/* Usage Stats */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <BarChart3 className="h-5 w-5" /> API Usage
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingUsage ? (
                <div className="text-center py-4 text-muted-foreground text-sm">Loading...</div>
              ) : apiUsage ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-3 rounded-lg bg-muted">
                      <p className="text-2xl font-bold">{apiUsage.total_requests.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">Total Requests</p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-muted">
                      <p className="text-2xl font-bold">{apiUsage.requests_today}</p>
                      <p className="text-xs text-muted-foreground">Today</p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-muted">
                      <p className="text-2xl font-bold">{apiUsage.requests_this_week}</p>
                      <p className="text-xs text-muted-foreground">This Week</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">Top Endpoints</p>
                    <div className="space-y-2">
                      {apiUsage.top_endpoints.map((ep) => (
                        <div key={ep.endpoint} className="flex items-center justify-between">
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                            {ep.endpoint}
                          </code>
                          <span className="text-sm font-mono">{ep.count.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Activity className="h-5 w-5" /> Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {activity.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between p-2 rounded border"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <div>
                        <p className="text-sm font-medium">{entry.action}</p>
                        <p className="text-xs text-muted-foreground">{entry.resource}</p>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {entry.timestamp}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
