"use client";

import { api } from "@/lib/api";

/** The shared API client, it attaches the access token and renews it on 401. */
const useAxiosAuth = () => api;

export default useAxiosAuth;
