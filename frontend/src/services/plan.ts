import type {
  Activity,
  ActivityType,
  BudgetAlertEvent,
  BudgetBreakdown,
  DayPlan,
  MessageEvent,
  PartialEvent,
  Period,
  PlanStepEvent,
  RhythmAdjustment,
  TripPlanRequest,
  TripPlanResponse,
  WeatherKind,
  WeatherSwap,
  WeatherSwapEvent,
} from "../types/trip";
import { postEventStream } from "./sse";
import { api, ApiError } from "./api";

interface CreatePlanOptions {
  onStep?: (event: PlanStepEvent) => void;
  onPartial?: (payload: PartialEvent) => void;
  onBudgetAlert?: (payload: BudgetAlertEvent) => void;
  onWeatherSwap?: (payload: WeatherSwapEvent) => void;
  onMessage?: (payload: MessageEvent) => void;
}

const ACTIVITY_TYPE_BY_VALUE: Record<string, ActivityType> = {
  景点: "景点",
  美食: "美食",
  室内: "室内",
  户外: "户外",
  文化: "文化",
  冒险: "冒险",
  留白: "留白",
  sightseeing: "景点",
  dining: "美食",
  indoor: "室内",
  outdoor: "户外",
  culture: "文化",
  adventure: "冒险",
  rest: "留白",
  自然: "景点",
  历史: "文化",
};

const PERIOD_BY_VALUE: Record<string, Period> = {
  上午: "上午",
  下午: "下午",
  晚间: "晚间",
  morning: "上午",
  afternoon: "下午",
  evening: "晚间",
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function addDays(date: string, amount: number): string {
  const parsed = new Date(`${date}T00:00:00`);

  if (Number.isNaN(parsed.getTime())) {
    return date;
  }

  parsed.setDate(parsed.getDate() + amount);
  const year = parsed.getFullYear();
  const month = `${parsed.getMonth() + 1}`.padStart(2, "0");
  const day = `${parsed.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function normalizeActivityType(value: unknown): ActivityType {
  return ACTIVITY_TYPE_BY_VALUE[asString(value)] ?? "景点";
}

function normalizePeriod(value: unknown): Period {
  return PERIOD_BY_VALUE[asString(value)] ?? "上午";
}

function normalizeWeatherKind(
  condition: string,
  value: unknown,
): WeatherKind | null {
  const kind = asNullableString(value);

  if (kind && ["sunny", "cloudy", "rainy", "windy", "hot", "snowy"].includes(kind)) {
    return kind as WeatherKind;
  }

  if (/雨|雷/.test(condition)) {
    return "rainy";
  }

  if (/雪/.test(condition)) {
    return "snowy";
  }

  if (/风/.test(condition)) {
    return "windy";
  }

  if (/晴/.test(condition)) {
    return "sunny";
  }

  if (/高温|热/.test(condition)) {
    return "hot";
  }

  return "cloudy";
}

function normalizeActivity(value: unknown): Activity {
  const activity = asRecord(value);

  return {
    name: asString(activity.name, "未命名活动"),
    activity_type: normalizeActivityType(
      activity.activity_type ?? activity.type,
    ),
    period: normalizePeriod(activity.period),
    start_time: asNullableString(activity.start_time),
    duration_min: asNumber(activity.duration_min, 60),
    description: asString(activity.description),
    estimated_cost: asNumber(activity.estimated_cost),
    location: asNullableString(activity.location),
    weather_note: asNullableString(activity.weather_note),
    couple_note: asNullableString(activity.couple_note),
    indoor_backup: asNullableString(activity.indoor_backup),
  };
}

function normalizeDay(
  value: unknown,
  index: number,
  startDate: string,
): DayPlan {
  const day = asRecord(value);
  const activities = asArray(day.activities).map(normalizeActivity);
  const weatherCondition = asString(
    day.weather_condition ?? day.weather,
    "晴",
  );
  const dailyCost = asNumber(
    day.daily_cost,
    activities.reduce((sum, activity) => sum + activity.estimated_cost, 0),
  );

  return {
    day_index: asNumber(day.day_index, index),
    trip_date: asString(day.trip_date, addDays(startDate, index)),
    weather_condition: weatherCondition,
    weather_kind: normalizeWeatherKind(weatherCondition, day.weather_kind),
    weather_high: typeof day.weather_high === "number" ? day.weather_high : null,
    weather_low: typeof day.weather_low === "number" ? day.weather_low : null,
    activities,
    daily_cost: dailyCost,
    day_note: asNullableString(day.day_note),
  };
}

function normalizeBudget(
  value: unknown,
  fallbackBudget: number,
  days: DayPlan[],
): BudgetBreakdown {
  const budget = asRecord(value);
  const totalBudget = asNumber(budget.total_budget, fallbackBudget);
  const totalSpent = asNumber(
    budget.total_spent,
    days.reduce((sum, day) => sum + day.daily_cost, 0),
  );
  const warningLevel = ["ok", "warning", "over"].includes(
    asString(budget.warning_level),
  )
    ? (asString(budget.warning_level) as "ok" | "warning" | "over")
    : totalSpent > totalBudget
      ? "over"
      : totalSpent / Math.max(totalBudget, 1) >= 0.9
        ? "warning"
        : "ok";

  return {
    total_budget: totalBudget,
    total_spent: totalSpent,
    by_day: asArray(budget.by_day)
      .map((item) => asNumber(item))
      .slice(0, days.length),
    over_budget:
      typeof budget.over_budget === "boolean"
        ? budget.over_budget
        : totalSpent > totalBudget,
    warning_level: warningLevel,
    spending_ratio: asNumber(
      budget.spending_ratio,
      totalSpent / Math.max(totalBudget, 1),
    ),
    downgrade_applied:
      typeof budget.downgrade_applied === "boolean"
        ? budget.downgrade_applied
        : false,
    downgrade_notes: asArray(budget.downgrade_notes).map((item) =>
      asString(item),
    ),
  };
}

function normalizeWeatherSwaps(value: unknown): WeatherSwap[] {
  return asArray(value).map((item) => {
    const swap = asRecord(item);
    return {
      day_index: asNumber(swap.day_index),
      original_name: asString(swap.original_name),
      replacement_name: asString(swap.replacement_name),
      reason: asString(swap.reason),
      adjustment_type:
        swap.adjustment_type === "time_shift" ? "time_shift" : "swap",
    };
  });
}

function normalizeRhythmAdjustments(value: unknown): RhythmAdjustment[] {
  return asArray(value).map((item) => {
    const adj = asRecord(item);
    const dropped = asArray(adj.dropped).map((d) => asString(d));
    return {
      day_index: asNumber(adj.day_index),
      period: asString(adj.period),
      kind: adj.kind === "inject_rest" ? "inject_rest" : "cap",
      reason: asString(adj.reason),
      dropped: dropped.length > 0 ? dropped : null,
    };
  });
}

function normalizePlan(
  value: unknown,
  request: TripPlanRequest,
): TripPlanResponse {
  const plan = asRecord(value);
  const days = asArray(plan.days).map((day, index) =>
    normalizeDay(day, index, request.start_date),
  );

  return {
    plan_id: asString(plan.plan_id, `plan-${Date.now()}`),
    destination: asString(plan.destination, request.destination),
    start_date: asString(plan.start_date, request.start_date),
    end_date: asString(plan.end_date, request.end_date),
    budget_breakdown: normalizeBudget(
      plan.budget_breakdown,
      request.budget,
      days,
    ),
    days,
    couple_notes: asArray(plan.couple_notes).map((note) => asString(note)),
    weather_swaps: normalizeWeatherSwaps(plan.weather_swaps),
    rhythm_adjustments: normalizeRhythmAdjustments(plan.rhythm_adjustments),
    status: asString(plan.status, "completed"),
  };
}

function readErrorMessage(payload: unknown): string {
  if (typeof payload === "string") {
    return payload;
  }

  const error = asRecord(payload);
  const message = error.message ?? error.detail;
  return asString(message, "行程生成失败，请稍后重试");
}

/**
 * 提交行程规划请求，解析后端 POST /api/plan 的 SSE 流并返回真实行程结果。
 */
export async function createPlan(
  request: TripPlanRequest,
  options: CreatePlanOptions = {},
): Promise<TripPlanResponse> {
  let plan: TripPlanResponse | null = null;

  await postEventStream("/api/plan", {
    body: request,
    onStep: options.onStep,
    onPartial: options.onPartial,
    onBudgetAlert: options.onBudgetAlert,
    onWeatherSwap: options.onWeatherSwap,
    onMessage: options.onMessage,
    onComplete: (payload) => {
      plan = normalizePlan(payload, request);
    },
    onError: (payload) => {
      throw new Error(readErrorMessage(payload));
    },
  });

  if (!plan) {
    throw new Error("未收到完整行程结果");
  }

  return plan;
}

/**
 * 通过 plan_id 从后端 REST 端点恢复已完成的行程（刷新恢复用）。
 * 返回 null 表示行程不存在或后端不可达。
 */
export async function fetchPlan(planId: string): Promise<TripPlanResponse | null> {
  try {
    const response = await api.get(`/api/plan/${planId}`);
    const record = response.data as {
      response?: unknown;
      status?: string;
      request?: TripPlanRequest;
    };

    if (!record.response) {
      return null;
    }

    const request = record.request ?? DEFAULT_REQUEST;
    return normalizePlan(record.response, request);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    return null;
  }
}

const DEFAULT_REQUEST: TripPlanRequest = {
  origin: "",
  destination: "",
  start_date: "",
  end_date: "",
  budget: 0,
  preferences: [],
  pace: "轻松",
};
