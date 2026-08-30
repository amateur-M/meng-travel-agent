export type Pace = "轻松" | "适中" | "充实";

export type Period = "上午" | "下午" | "晚间";

export type ActivityType =
  | "景点"
  | "美食"
  | "室内"
  | "户外"
  | "文化"
  | "冒险"
  | "留白";

export type WeatherKind =
  | "sunny"
  | "cloudy"
  | "rainy"
  | "windy"
  | "hot"
  | "snowy";

export type PlanStatus = "idle" | "planning" | "ready" | "error";

export interface TripPlanRequest {
  origin: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget: number;
  preferences: string[];
  pace: Pace;
}

export interface Activity {
  name: string;
  activity_type: ActivityType;
  period: Period;
  start_time?: string | null;
  duration_min: number;
  description: string;
  estimated_cost: number;
  location?: string | null;
  weather_note?: string | null;
  couple_note?: string | null;
  indoor_backup?: string | null;
}

export interface DayPlan {
  day_index: number;
  trip_date: string;
  weather_condition: string;
  weather_kind?: WeatherKind | null;
  weather_high?: number | null;
  weather_low?: number | null;
  activities: Activity[];
  daily_cost: number;
  day_note?: string | null;
}

export interface BudgetBreakdown {
  total_budget: number;
  total_spent: number;
  by_day: number[];
  over_budget: boolean;
  warning_level: "ok" | "warning" | "over";
  spending_ratio: number;
  downgrade_applied: boolean;
  downgrade_notes: string[];
}

export interface WeatherSwap {
  day_index: number;
  original_name: string;
  replacement_name: string;
  reason: string;
  adjustment_type: "swap" | "time_shift";
}

export interface TripPlanResponse {
  plan_id: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget_breakdown: BudgetBreakdown;
  days: DayPlan[];
  couple_notes: string[];
  weather_swaps: WeatherSwap[];
  status: string;
}

export interface PlanStepEvent {
  phase: string;
  message: string;
}

export interface PlanningStep {
  id: string;
  label: string;
  description: string;
  status: "pending" | "active" | "done";
}

export type Theme = "light" | "dark";
