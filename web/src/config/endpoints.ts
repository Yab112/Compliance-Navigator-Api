export const endpoints = {
  auth: {
    login: {
      query: "login",
      endpoint: "/users/login",
    },
    register: {
      query: "register",
      endpoint: "/users",
    },
    me: {
      query: "me",
      endpoint: "/auth/me",
    },
    logout: {
      query: "logout",
      endpoint: "/auth/logout",
    },
  },
};
