import type {
  PlanStepEvent,
  TripPlanRequest,
  TripPlanResponse,
} from "../types/trip";

interface PlanStreamOptions {
  onStep?: (event: PlanStepEvent) => void;
}

export async function createPlan(
  request: TripPlanRequest,
  options: PlanStreamOptions = {},
): Promise<TripPlanResponse> {
  const response = await fetch("/api/plan", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `计划请求失败：${response.status}`);
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let plan: TripPlanResponse | null = null;

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

      if (event.event === "step") {
        options.onStep?.(event.data as PlanStepEvent);
      }

      if (event.event === "complete") {
        plan = event.data as TripPlanResponse;
      }

      if (event.event === "error") {
        const errorData = event.data as { message?: unknown } | null;
        const message =
          errorData && typeof errorData.message === "string"
            ? errorData.message
            : "行程生成失败";
        throw new Error(message);
      }
    }
  }

  if (!plan) {
    throw new Error("未收到完整行程结果");
  }

  return plan;
}

function parseSseEvent(rawEvent: string) {
  let event = "";
  const dataLines: string[] = [];

  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!event || dataLines.length === 0) {
    return null;
  }

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    data = dataLines.join("\n");
  }

  return { event, data };
}
