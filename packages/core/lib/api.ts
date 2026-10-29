import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { env } from "../config/env";
import { getAccessToken } from "./auth-token";
import { refreshSession } from "./auth-session";

export type { APIResponse } from "../types/global";

export const api = axios.create({
  baseURL: env.NEXT_PUBLIC_API_BASE_URL,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

// An expired access token is renewed once from the refresh cookie and the request replayed
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthCall = /^\/?auth\/(refresh|login|register|logout)/.test(config?.url ?? "");
    if (error.response?.status !== 401 || !config || config._retried || isAuthCall) {
      return Promise.reject(error);
    }
    config._retried = true;
    if (!(await refreshSession())) return Promise.reject(error);
    config.headers.Authorization = `Bearer ${getAccessToken()}`;
    return api.request(config);
  },
);

/** Absolute URL for files the API serves (e.g. /uploads/public/…). */
export function apiAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  const origin = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/api\/v1\/?$/, "");
  return `${origin}${path.startsWith("/") ? "" : "/"}${path}`;
}
