import type {
  PlanStepEvent,
  PartialEvent,
  BudgetAlertEvent,
  WeatherSwapEvent,
  MessageEvent as CoupleMessageEvent,
} from "../types/trip";

export interface SSEHandlers {
  onStep?: (event: PlanStepEvent) => void;
  onPartial?: (payload: PartialEvent) => void;
  onBudgetAlert?: (payload: BudgetAlertEvent) => void;
  onWeatherSwap?: (payload: WeatherSwapEvent) => void;
  onMessage?: (payload: CoupleMessageEvent) => void;
  onComplete?: (payload: unknown) => void;
  onError?: (payload: unknown) => void;
}

// P3.1: 构建带 X-API-Key 的请求头（仅当构建时注入了 VITE_API_KEY）。
const API_KEY_HEADER: Record<string, string> = import.meta.env.VITE_API_KEY
  ? { "X-API-Key": import.meta.env.VITE_API_KEY }
  : {};

interface PostStreamHandlers {
  body: unknown;
  onStep?: (event: PlanStepEvent) => void;
  onPartial?: (payload: PartialEvent) => void;
  onBudgetAlert?: (payload: BudgetAlertEvent) => void;
  onWeatherSwap?: (payload: WeatherSwapEvent) => void;
  onMessage?: (payload: CoupleMessageEvent) => void;
  onComplete?: (payload: unknown) => void;
  onError?: (payload: unknown) => void;
  maxRetries?: number;
}

/**
 * 建立并管理一条基于 EventSource 的 GET SSE 连接。
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

const MAX_RETRIES = 2;

/**
 * 通过 POST + ReadableStream 消费 SSE。当前后端 /api/plan 是 POST 接口，
 * EventSource 无法携带请求体，因此这里用 fetch 手动解析事件流。
 *
 * M6: 支持全部事件类型（step/partial/budget_alert/weather_swap/message/
 * complete/error），并在连接中断时自动重试（最多 maxRetries 次）。
 *
 * P0.3: 仍保留用于 POST /api/plan 直接流式（旧路径兼容），但新代码
 * 优先使用 startPlan + resumeStream 两段式。
 */
export async function postEventStream(
  url: string,
  handlers: PostStreamHandlers,
) {
  const maxRetries = handlers.maxRetries ?? MAX_RETRIES;
  let attempt = 0;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    let completed = false;

    try {
      await consumeOnce(url, handlers, () => {
        completed = true;
      });

      if (completed) {
        return;
      }

      // 流正常结束但未收到 complete —— 视为中断，尝试重试
      if (attempt >= maxRetries) {
        throw new Error("流式响应中断，已达最大重试次数");
      }
      attempt += 1;
      await delay(800 * attempt);
    } catch (error) {
      // fetch 网络错误或流中途断开
      if (attempt >= maxRetries) {
        throw error;
      }
      attempt += 1;
      await delay(800 * attempt);
    }
  }
}

/**
 * P0.3: 通过 GET + ReadableStream 消费 SSE 流。
 *
 * 用于消费 GET /api/plan/{plan_id}/stream 端点。断线重连时自动
 * 重连同一个 GET URL，不会重新发起 POST 创建新 plan。
 */
export async function getEventStream(
  url: string,
  handlers: SSEHandlers,
  maxRetries: number = MAX_RETRIES,
) {
  let attempt = 0;
  let receivedComplete = false;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    let streamEnded = false;

    try {
      await consumeGetOnce(url, handlers, () => {
        receivedComplete = true;
        streamEnded = true;
      }, () => {
        streamEnded = true;
      });

      if (receivedComplete) {
        return;
      }

      // 流结束但未收到 complete —— 可能中断，重连同一 URL
      if (!streamEnded || attempt >= maxRetries) {
        throw new Error("流式响应中断，已达最大重试次数");
      }
      attempt += 1;
      await delay(800 * attempt);
    } catch (error) {
      if (attempt >= maxRetries) {
        throw error;
      }
      attempt += 1;
      await delay(800 * attempt);
    }
  }
}

async function consumeGetOnce(
  url: string,
  handlers: SSEHandlers,
  markComplete: () => void,
  markEnded: () => void,
) {
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      ...API_KEY_HEADER,
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败（${response.status}）`);
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      markEnded();
      return;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const event = parseSseEvent(rawEvent);

      if (!event) {
        continue;
      }

      if (event.name === "step") {
        handlers.onStep?.(event.data as PlanStepEvent);
      } else if (event.name === "partial") {
        handlers.onPartial?.(event.data as PartialEvent);
      } else if (event.name === "budget_alert") {
        handlers.onBudgetAlert?.(event.data as BudgetAlertEvent);
      } else if (event.name === "weather_swap") {
        handlers.onWeatherSwap?.(event.data as WeatherSwapEvent);
      } else if (event.name === "message") {
        handlers.onMessage?.(event.data as CoupleMessageEvent);
      } else if (event.name === "complete") {
        markComplete();
        handlers.onComplete?.(event.data);
      } else if (event.name === "error") {
        throw new Error(
          typeof event.data === "object" && event.data !== null
            ? ((event.data as { message?: string }).message ??
              "行程生成失败")
            : String(event.data),
        );
      }
    }
  }
}

async function consumeOnce(
  url: string,
  handlers: PostStreamHandlers,
  markComplete: () => void,
) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...API_KEY_HEADER,
    },
    body: JSON.stringify(handlers.body),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败（${response.status}）`);
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      return;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const event = parseSseEvent(rawEvent);

      if (!event) {
        continue;
      }

      if (event.name === "step") {
        handlers.onStep?.(event.data as PlanStepEvent);
      } else if (event.name === "partial") {
        handlers.onPartial?.(event.data as PartialEvent);
      } else if (event.name === "budget_alert") {
        handlers.onBudgetAlert?.(event.data as BudgetAlertEvent);
      } else if (event.name === "weather_swap") {
        handlers.onWeatherSwap?.(event.data as WeatherSwapEvent);
      } else       if (event.name === "message") {
        handlers.onMessage?.(event.data as CoupleMessageEvent);
      } else if (event.name === "complete") {
        markComplete();
        handlers.onComplete?.(event.data);
      } else if (event.name === "error") {
        throw new Error(
          typeof event.data === "object" && event.data !== null
            ? ((event.data as { message?: string }).message ??
              "行程生成失败")
            : String(event.data),
        );
      }
    }
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseSseEvent(rawEvent: string) {
  let name = "";
  const dataLines: string[] = [];

  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      name = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!name || dataLines.length === 0) {
    return null;
  }

  let data: unknown;

  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    data = dataLines.join("\n");
  }

  return { name, data };
}
