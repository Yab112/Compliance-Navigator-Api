"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError, type AxiosRequestConfig } from "axios";
import useAxiosAuth from "./use-axios-auth";

export type MutationOptions<TRequestBody = unknown> = {
  url: string;
  method: AxiosRequestConfig["method"];
  body?: TRequestBody;
  params?: Record<string, string | number | boolean>;
  headers?: AxiosRequestConfig["headers"];
  timeout?: number;
  responseType?: AxiosRequestConfig["responseType"];
};

export type ApiErrorResponse = {
  message?: string;
  code?: number | string;
  errors?: unknown[];
};

interface UseMutationFuncOptions<
  TResponseData,
  TRequestBody,
  TError = ApiErrorResponse,
> {
  onSuccess?: (
    data: TResponseData,
    options: MutationOptions<TRequestBody>,
  ) => void;
  onError?: (
    error: TError,
    options?: MutationOptions<TRequestBody>,
    context?: { previousData: unknown },
  ) => void;
  onMutate?: (
    oldData: unknown,
    options: MutationOptions<TRequestBody>,
  ) => unknown;
  queryKey?: (string | number)[];
  defaultErrorMessage?: string;
}

const useMutationFunc = <TResponseData, TRequestBody, TError = ApiErrorResponse>(
  options?: UseMutationFuncOptions<TResponseData, TRequestBody, TError>,
) => {
  const axiosAuth = useAxiosAuth();
  const queryClient = useQueryClient();

  return useMutation<
    TResponseData,
    TError,
    MutationOptions<TRequestBody>,
    { previousData: unknown }
  >({
    mutationFn: async (mutationOptions) => {
      const { url, method, body, params, headers, timeout, responseType } =
        mutationOptions;
      const path = url.startsWith("/") ? url : `/${url}`;
      const response = await axiosAuth.request<TResponseData>({
        url: path,
        method,
        headers,
        ...(params != null &&
          Object.keys(params).length > 0 && { params }),
        ...(body !== undefined && { data: body }),
        ...(timeout != null && { timeout }),
        ...(responseType != null && { responseType }),
      });
      return response.data;
    },
    onMutate: (mutationOptions) => {
      if (!options?.queryKey || !options?.onMutate) {
        return { previousData: undefined };
      }
      queryClient.cancelQueries({ queryKey: options.queryKey });
      const previousData = queryClient.getQueryData(options.queryKey);
      queryClient.setQueryData(options.queryKey, (oldData: unknown) =>
        options.onMutate?.(oldData, mutationOptions) ?? oldData,
      );
      return { previousData };
    },
    onSuccess: (data, mutationOptions) => {
      options?.onSuccess?.(data, mutationOptions);
      if (options?.queryKey) {
        queryClient.invalidateQueries({
          queryKey: options.queryKey,
          exact: true,
        });
      }
    },
    onError: (error, mutationOptions, context) => {
      if (context?.previousData && options?.queryKey) {
        queryClient.setQueryData(options.queryKey, context.previousData);
      }
      let message: string;
      let code: number | string | undefined;
      if (error instanceof AxiosError) {
        code = error.code === "ERR_NETWORK" ? 500 : error.response?.status;
        if (error.response?.status === 403) {
          message =
            (error.response?.data as { message?: string })?.message ||
            "You don't have permission to perform this action.";
        } else if (error.code === "ERR_NETWORK") {
          message = "Network error occurred";
        } else {
          message =
            (error.response?.data as { message?: string })?.message ||
            options?.defaultErrorMessage ||
            "An error occurred";
        }
      } else {
        message =
          (error as { message?: string })?.message ?? "An error occurred";
        code = undefined;
      }
      const errorToThrow = {
        message,
        code,
        errors:
          error instanceof AxiosError
            ? (error.response?.data as { errors?: unknown[] })?.errors || []
            : [],
      } as TError;
      options?.onError?.(errorToThrow, mutationOptions, context);
    },
  });
};

export default useMutationFunc;
