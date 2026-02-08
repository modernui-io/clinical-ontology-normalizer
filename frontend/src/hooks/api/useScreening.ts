/**
 * Bulk Screening React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  runBulkScreening,
  getScreeningResults,
  type BulkScreeningRequest,
  type BulkScreeningResponse,
  type ScreeningResultListResponse,
  type ScreeningResultListParams,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useBulkScreening() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: BulkScreeningRequest) => runBulkScreening(body),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.screening.all,
      });
    },
  });
}

export function useScreeningResults(
  params?: ScreeningResultListParams,
  options?: Omit<UseQueryOptions<ScreeningResultListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.screening.list(params),
    queryFn: () => getScreeningResults(params),
    ...options,
  });
}
