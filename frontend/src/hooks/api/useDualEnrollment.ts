/**
 * Dual Enrollment Detection React Query hooks.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  findDualEnrollmentCandidates,
  type DualEnrollmentRequest,
  type DualEnrollmentResponse,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

/**
 * Mutation hook to find dual enrollment candidates.
 * Uses mutation (not query) because this is an on-demand POST action
 * triggered by a button click rather than automatic data fetching.
 */
export function useDualEnrollmentCandidates() {
  const queryClient = useQueryClient();

  return useMutation<DualEnrollmentResponse, Error, DualEnrollmentRequest | undefined>({
    mutationFn: (request) => findDualEnrollmentCandidates(request),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.trials.all,
      });
    },
  });
}
