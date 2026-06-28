import { User } from "@/types";

export const MOCK_TOKEN = "mock-dev-session";
export const MOCK_EMAIL = "eshetieyabibal@gmail.com";
export const MOCK_PASSWORD = "test@123";

export const MOCK_USER: User = {
  id: "mock-user-1",
  email: MOCK_EMAIL,
  fullname: "Yabibal Eshetie Molla",
};

export function isMockCredentials(email: string, password: string): boolean {
  return (
    email.trim().toLowerCase() === MOCK_EMAIL &&
    password === MOCK_PASSWORD
  );
}

export function isMockToken(token: string | null): boolean {
  return token === MOCK_TOKEN;
}
