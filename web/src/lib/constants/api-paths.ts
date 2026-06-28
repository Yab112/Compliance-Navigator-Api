/** API path segments (relative to NEXT_PUBLIC_API_BASE_URL, e.g. http://localhost:8080/api/v1) */
export const apiPaths = {
  auth: {
    me: "auth/me",
    logout: "auth/logout",
  },
  users: {
    register: "users",
    login: "users/login",
  },
  processes: "processes",
  roadmaps: "roadmaps",
  chat: "chat",
  chatTranscribe: "chat/transcribe",
} as const;
