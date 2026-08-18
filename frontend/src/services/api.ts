import axios, { AxiosError } from "axios";

/**
 * 统一 Axios 实例。所有 REST 请求共享同一份 baseURL、超时和响应错误归一化逻辑。
 */
export const api = axios.create({
  baseURL: "/",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

export class ApiError extends Error {
  status?: number;
  code?: string;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const payload = error.response?.data as
      | { message?: unknown; detail?: unknown; code?: unknown }
      | undefined;

    const rawMessage =
      typeof payload?.message === "string"
        ? payload.message
        : typeof payload?.detail === "string"
          ? payload.detail
          : undefined;

    const code =
      typeof payload?.code === "string" ? payload.code : undefined;

    return Promise.reject(
      new ApiError(rawMessage ?? "请求失败，请稍后重试", status, code),
    );
  },
);
