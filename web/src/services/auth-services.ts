import { api, APIResponse, TokenResponse } from "@/lib/api";
import { endpoints } from "@/config/endpoints";
import { clearAccessToken, setAccessToken } from "@/lib/auth-token";
import { User } from "@/types";

export namespace AuthServices {
  export async function login(email: string, password: string) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);

    const { data } = await api.post<TokenResponse>(
      endpoints.auth.login.endpoint,
      form,
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
    );

    setAccessToken(data.access_token);
    return data;
  }

  export async function register(input: {
    email: string;
    password: string;
    fullname: string;
  }) {
    const { data } = await api.post<APIResponse<{ user: User }>>(
      endpoints.auth.register.endpoint,
      input,
    );
    return data;
  }

  export function getMe() {
    return api.get<APIResponse<{ user: User }>>(endpoints.auth.me.endpoint);
  }

  export async function logout() {
    try {
      await api.post<APIResponse<null>>(endpoints.auth.logout.endpoint);
    } finally {
      clearAccessToken();
    }
  }
}
