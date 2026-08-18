import type { PlanStepEvent } from "../types/trip";

interface SSEHandlers {
  onStep?: (event: PlanStepEvent) => void;
  onPartial?: (payload: unknown) => void;
  onBudgetAlert?: (payload: unknown) => void;
  onWeatherSwap?: (payload: unknown) => void;
  onMessage?: (payload: unknown) => void;
  onComplete?: (payload: unknown) => void;
  onError?: (payload: unknown) => void;
}

/**
 * 建立并管理一条 SSE 连接。调用方拿到 close 方法后，可在组件卸载时安全释放连接。
 */
export function connectSSE(url: string, handlers: SSEHandlers) {
  const source = new EventSource(url);

  const subscribe = <T,>(name: string, handler?: (payload: T) => void) => {
    if (!handler) {
      return;
    }

    source.addEventListener(name, (event) => {
      let payload: unknown;

      try {
        payload = JSON.parse((event as MessageEvent<string>).data);
      } catch {
        payload = (event as MessageEvent<string>).data;
      }

      handler(payload as T);
    });
  };

  subscribe("step", handlers.onStep);
  subscribe("partial", handlers.onPartial);
  subscribe("budget_alert", handlers.onBudgetAlert);
  subscribe("weather_swap", handlers.onWeatherSwap);
  subscribe("message", handlers.onMessage);
  subscribe("complete", handlers.onComplete);
  subscribe("error", handlers.onError);

  return {
    close: () => source.close(),
  };
}
