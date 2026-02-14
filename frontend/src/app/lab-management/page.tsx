"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Microscope,
  Building2,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";

interface Certification {
  name: string;
  number: string;
  expiry: string;
  status: string;
}

interface Lab {
  id: string;
  name: string;
  lab_type: string;
  address: string;
  country: string;
  contact_name: string;
  contact_email: string;
  phone: string;
  active: boolean;
  capabilities: string[];
  certifications: Certification[];
}

interface LabsResponse {
  items: Lab[];
  total: number;
}

export default function LabManagementPage() {
  const [labs, setLabs] = useState<Lab[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLabs();
  }, []);

  const fetchLabs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/lab-certification/labs");
      if (!response.ok) {
        throw new Error("Failed to fetch labs");
      }
      const data: LabsResponse = await response.json();
      setLabs(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const getLabTypeBadgeVariant = (labType: string): "default" | "secondary" | "outline" => {
    switch (labType) {
      case "central":
        return "default";
      case "local":
        return "secondary";
      case "specialty":
        return "outline";
      default:
        return "secondary";
    }
  };

  const getCertificationStatus = (certification: Certification) => {
    const expiryDate = new Date(certification.expiry);
    const today = new Date();
    const daysUntilExpiry = Math.floor(
      (expiryDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
    );

    if (daysUntilExpiry < 0) {
      return { variant: "expired", Icon: AlertCircle, color: "text-red-600" };
    } else if (daysUntilExpiry <= 30) {
      return { variant: "critical", Icon: AlertTriangle, color: "text-red-500" };
    } else if (daysUntilExpiry <= 90) {
      return { variant: "warning", Icon: AlertTriangle, color: "text-amber-500" };
    } else {
      return { variant: "active", Icon: CheckCircle, color: "text-emerald-500" };
    }
  };

  const certificationStats = labs.reduce(
    (acc, lab) => {
      lab.certifications.forEach((cert) => {
        const status = getCertificationStatus(cert);
        if (status.variant === "warning" || status.variant === "critical" || status.variant === "expired") {
          acc.expiringSoon++;
        }
      });
      return acc;
    },
    { expiringSoon: 0 }
  );

  const totalCapabilities = new Set(labs.flatMap((lab) => lab.capabilities)).size;
  const activeLabs = labs.filter((lab) => lab.active).length;

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Loading lab data...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 space-y-6">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-red-800">
              <AlertCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">Error loading lab data</p>
                <p className="text-sm text-red-600">{error}</p>
              </div>
            </div>
            <Button
              onClick={fetchLabs}
              variant="outline"
              size="sm"
              className="mt-4"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Lab Management</h1>
          <p className="text-muted-foreground">
            Laboratory certification and capability management
          </p>
        </div>
        <Button onClick={fetchLabs} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Microscope className="h-4 w-4" />
              Total Labs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{labs.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              Active Labs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeLabs}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Certifications Expiring Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {certificationStats.expiringSoon}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              Total Capabilities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCapabilities}</div>
          </CardContent>
        </Card>
      </div>

      {/* Lab Cards */}
      <div className="space-y-4">
        {labs.map((lab) => (
          <Card key={lab.id}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{lab.name}</CardTitle>
                    <Badge
                      variant={getLabTypeBadgeVariant(lab.lab_type)}
                      className={
                        lab.lab_type === "central"
                          ? "bg-blue-500 text-white"
                          : lab.lab_type === "specialty"
                          ? "border-purple-500 text-purple-700"
                          : ""
                      }
                    >
                      {lab.lab_type}
                    </Badge>
                    {lab.active && (
                      <Badge variant="outline" className="border-emerald-500 text-emerald-700">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Active
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {lab.id}
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Contact Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="font-medium text-muted-foreground mb-1">Address</p>
                  <p>{lab.address}</p>
                  <p className="text-muted-foreground">{lab.country}</p>
                </div>
                <div>
                  <p className="font-medium text-muted-foreground mb-1">Contact</p>
                  <p>{lab.contact_name}</p>
                  <p className="text-muted-foreground">{lab.contact_email}</p>
                  <p className="text-muted-foreground">{lab.phone}</p>
                </div>
              </div>

              {/* Capabilities */}
              <div>
                <p className="font-medium text-sm text-muted-foreground mb-2">
                  Capabilities
                </p>
                <div className="flex flex-wrap gap-2">
                  {lab.capabilities.map((capability) => (
                    <Badge key={capability} variant="secondary" className="text-xs">
                      {capability}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Certifications */}
              <div>
                <p className="font-medium text-sm text-muted-foreground mb-2">
                  Certifications
                </p>
                <div className="space-y-2">
                  {lab.certifications.map((cert) => {
                    const status = getCertificationStatus(cert);
                    const expiryDate = new Date(cert.expiry);
                    const today = new Date();
                    const daysUntilExpiry = Math.floor(
                      (expiryDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
                    );

                    return (
                      <div
                        key={cert.number}
                        className={`flex items-center justify-between p-3 rounded-lg border ${
                          status.variant === "expired"
                            ? "border-red-200 bg-red-50"
                            : status.variant === "critical"
                            ? "border-red-200 bg-red-50"
                            : status.variant === "warning"
                            ? "border-amber-200 bg-amber-50"
                            : "border-gray-200 bg-gray-50"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <status.Icon className={`h-4 w-4 ${status.color}`} />
                          <div>
                            <p className="font-medium text-sm">
                              {cert.name}{" "}
                              <span className="text-muted-foreground font-normal">
                                {cert.number}
                              </span>
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Expires: {expiryDate.toLocaleDateString()}
                              {daysUntilExpiry >= 0 && daysUntilExpiry <= 90 && (
                                <span
                                  className={
                                    daysUntilExpiry <= 30
                                      ? "text-red-600 font-medium ml-2"
                                      : "text-amber-600 font-medium ml-2"
                                  }
                                >
                                  ({daysUntilExpiry} days)
                                </span>
                              )}
                              {daysUntilExpiry < 0 && (
                                <span className="text-red-600 font-medium ml-2">
                                  (Expired)
                                </span>
                              )}
                            </p>
                          </div>
                        </div>
                        <Badge
                          variant={
                            cert.status === "active" ? "outline" : "secondary"
                          }
                          className={
                            cert.status === "active"
                              ? "border-emerald-500 text-emerald-700"
                              : ""
                          }
                        >
                          {cert.status}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {labs.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground py-12">
              <Microscope className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="font-medium">No labs found</p>
              <p className="text-sm">Lab data will appear here when available</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
