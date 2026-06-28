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

  return useQuery<T>({
    queryKey,
    queryFn: async () => {
      try {
        const response = await axiosAuth.get<T>(path);
        options?.onSuccess?.(response.data);
        return response.data;
      } catch (error) {
        if (error instanceof AxiosError) {
          const networkError = error.code === "ERR_NETWORK";
          const message = networkError
            ? error.message
            : (error.response?.data as { message?: string })?.message;
          throw new Error(message ?? "Request failed");
        }
        throw error;
      }
    },
    ...(options?.refetchInterval && {
      refetchInterval: options.refetchInterval,
    }),
    staleTime: options?.staleTime ?? 5 * 60 * 1000,
    enabled: options?.enabled ?? true,
    placeholderData: keepPreviousData,
    refetchOnMount: options?.refetchOnMount,
    refetchOnWindowFocus: options?.refetchOnWindowFocus,
  });
};
