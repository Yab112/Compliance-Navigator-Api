import axios from "axios";
import { env } from "@/config/env";
import { getAccessToken } from "@/lib/auth-token";
import { MOCK_TOKEN } from "@/lib/mock-auth";

export type { APIResponse } from "@/types/global";

export interface TokenResponse {
  access_token: string;
  type: string;
}

export const api = axios.create({
  baseURL: env.NEXT_PUBLIC_API_BASE_URL,
  withCredentials: false,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
