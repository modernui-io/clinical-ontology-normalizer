/**
 * Sites React Query hooks.
 */

import {
  useQuery,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  getSites,
  getSite,
  getSitePatients,
  getSiteScreeningSummary,
  type SiteListResponse,
  type SiteResponse,
  type SitePatientListResponse,
  type SiteScreeningSummary,
  type SiteListParams,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useSites(
  params?: SiteListParams,
  options?: Omit<UseQueryOptions<SiteListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.sites.list(params),
    queryFn: () => getSites(params),
    ...options,
  });
}

export function useSite(
  siteId: string,
  options?: Omit<UseQueryOptions<SiteResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.sites.detail(siteId),
    queryFn: () => getSite(siteId),
    enabled: !!siteId,
    ...options,
  });
}

export function useSitePatients(
  siteId: string,
  options?: Omit<UseQueryOptions<SitePatientListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.sites.patients(siteId),
    queryFn: () => getSitePatients(siteId),
    enabled: !!siteId,
    ...options,
  });
}

export function useSiteScreeningSummary(
  siteId: string,
  options?: Omit<UseQueryOptions<SiteScreeningSummary>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.sites.screening(siteId),
    queryFn: () => getSiteScreeningSummary(siteId),
    enabled: !!siteId,
    ...options,
  });
}
