"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useSite,
  useSitePatients,
  useSiteScreeningSummary,
} from "@/hooks/api/useSites";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  RefreshCw,
  Users,
  Target,
  MapPin,
  Building2,
  ClipboardList,
} from "lucide-react";

export default function SiteDetailPage() {
  const params = useParams();
  const siteId = params.id as string;

  const { data: site, isLoading: siteLoading } = useSite(siteId);
  const { data: patientsData } = useSitePatients(siteId);
  const { data: screening, isLoading: screeningLoading } =
    useSiteScreeningSummary(siteId);

  if (siteLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading site...</span>
      </div>
    );
  }

  if (!site) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Site not found.</p>
        <Link href="/sites">
          <Button variant="outline" className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Sites
          </Button>
        </Link>
      </div>
    );
  }

  const patients = patientsData?.patients || [];
  const screenedPercent =
    screening && screening.total_patients > 0
      ? Math.round(
          (screening.patients_screened / screening.total_patients) * 100
        )
      : 0;
  const matchedPercent =
    screening && screening.patients_screened > 0
      ? Math.round(
          (screening.patients_matched / screening.patients_screened) * 100
        )
      : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link href="/sites">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-1 h-4 w-4" />
                Sites
              </Button>
            </Link>
          </div>
          <h1 className="text-2xl font-bold">{site.name}</h1>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            {site.site_code && (
              <Badge variant="outline" className="font-mono">
                {site.site_code}
              </Badge>
            )}
            {site.organization && (
              <span className="flex items-center gap-1 text-sm text-muted-foreground">
                <Building2 className="h-3.5 w-3.5" />
                {site.organization}
              </span>
            )}
            <span className="flex items-center gap-1 text-sm text-muted-foreground">
              <MapPin className="h-3.5 w-3.5" />
              {[site.address, site.city, site.state, site.country]
                .filter(Boolean)
                .join(", ") || "No location specified"}
            </span>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Patients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {screening?.total_patients ?? patients.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Screened</CardTitle>
            <ClipboardList className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {screening?.patients_screened ?? 0}
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-blue-500 transition-all"
                style={{ width: `${screenedPercent}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {screenedPercent}% of patients
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Matched</CardTitle>
            <Target className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {screening?.patients_matched ?? 0}
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-green-500 transition-all"
                style={{ width: `${matchedPercent}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {matchedPercent}% of screened
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Trial Matches</CardTitle>
            <Target className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {screening?.trial_matches?.length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              trials with matches
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Trial Matches Table */}
      <Card>
        <CardHeader>
          <CardTitle>Trial Matches</CardTitle>
          <CardDescription>
            Screening results per trial at this site
          </CardDescription>
        </CardHeader>
        <CardContent>
          {screeningLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">
                Loading screening summary...
              </span>
            </div>
          ) : !screening ||
            screening.trial_matches.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No trial matches found for this site
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Trial</TableHead>
                    <TableHead className="text-right">
                      Matched Patients
                    </TableHead>
                    <TableHead>Patient IDs</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {screening.trial_matches.map((match) => (
                    <TableRow key={match.trial_id}>
                      <TableCell>
                        <Link
                          href={`/trials/${match.trial_id}`}
                          className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {match.trial_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline">
                          {match.matched_patients}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {match.matched_patient_ids.map((pid) => (
                            <Link
                              key={pid}
                              href={`/patients/${pid}`}
                              className="text-xs font-mono text-blue-600 hover:underline dark:text-blue-400"
                            >
                              {pid.slice(0, 8)}...
                            </Link>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Patient Roster */}
      <Card>
        <CardHeader>
          <CardTitle>Patient Roster</CardTitle>
          <CardDescription>
            {patients.length} patient{patients.length !== 1 ? "s" : ""} assigned
            to this site
          </CardDescription>
        </CardHeader>
        <CardContent>
          {patients.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No patients assigned to this site
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Name</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {patients.map((patient) => (
                    <TableRow key={patient.patient_id}>
                      <TableCell className="font-mono text-sm">
                        <Link
                          href={`/patients/${patient.patient_id}`}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {patient.patient_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {patient.patient_name || (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
