import type { PlanStepEvent } from "../types/trip";

export interface SSEHandlers {
  onStep?: (event: PlanStepEvent) => void;
  onPartial?: (payload: unknown) => void;
  onBudgetAlert?: (payload: unknown) => void;
  onWeatherSwap?: (payload: unknown) => void;
  onMessage?: (payload: unknown) => void;
  onComplete?: (payload: unknown) => void;
  onError?: (payload: unknown) => void;
}

interface PostStreamHandlers {
  body: unknown;
  onStep?: (event: PlanStepEvent) => void;
  onComplete?: (payload: unknown) => void;
  onError?: (payload: unknown) => void;
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

/**
 * 通过 POST + ReadableStream 消费 SSE。当前后端 /api/plan 是 POST 接口，
 * EventSource 无法携带请求体，因此这里用 fetch 手动解析事件流。
 */
export async function postEventStream(
  url: string,
  handlers: PostStreamHandlers,
) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
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

  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      break;
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
      }

      if (event.name === "complete") {
        handlers.onComplete?.(event.data);
      }

      if (event.name === "error") {
        handlers.onError?.(event.data);
      }
    }
  }
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
