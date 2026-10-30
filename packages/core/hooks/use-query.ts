"use client";

import {
  type UseQueryOptions,
  type UseQueryResult,
  keepPreviousData,
  useQuery,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import useAxiosAuth from "./use-axios-auth";

type FetchDataOptions<T> = Omit<UseQueryOptions<T>, "queryKey" | "queryFn">;
type UseFetchDataOptions<T> = FetchDataOptions<T> & {
  onSuccess?: (data: T) => void;
};

export const useFetchData = <T>(
  queryKey: readonly unknown[],
  url: string,
  options?: UseFetchDataOptions<T>,
): UseQueryResult<T> => {
  const axiosAuth = useAxiosAuth();
  const path = url.startsWith("/") ? url : `/${url}`;
  // Every other TanStack option (retry, select, gcTime, refetchInterval…) is passed straight through
  const { onSuccess, ...queryOptions } = options ?? {};

  return useQuery<T>({
    placeholderData: keepPreviousData,
    ...queryOptions,
    staleTime: queryOptions.staleTime ?? 5 * 60 * 1000,
    queryKey,
    queryFn: async () => {
      try {
        const response = await axiosAuth.get<T>(path);
        onSuccess?.(response.data);
        return response.data;
      } catch (error) {
        if (error instanceof AxiosError) {
          const networkError = error.code === "ERR_NETWORK";
          const data = error.response?.data as
            | { message?: string; detail?: unknown }
            | undefined;
          const message = networkError
            ? error.message
            : (data?.message ??
              (typeof data?.detail === "string" ? data.detail : undefined));
          throw new Error(message ?? "Request failed");
        }
        throw error;
      }
    },
  });
};
