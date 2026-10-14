import { create } from "zustand";
import { createPlan, fetchPlan } from "../services/plan";
import type {
  Activity,
  BudgetAlertEvent,
  MessageEvent,
  PartialEvent,
  PlanningStep,
  PlanStatus,
  TripPlanRequest,
  TripPlanResponse,
  WeatherSwapEvent,
} from "../types/trip";

const DEFAULT_FORM: TripPlanRequest = {
  origin: "北京",
  destination: "大理",
  start_date: "2026-09-01",
  end_date: "2026-09-03",
  budget: 4500,
  preferences: ["浪漫", "美食", "自然"],
  pace: "轻松",
};

const PLANNING_STEPS: PlanningStep[] = [
  {
    id: "parse",
    label: "理解旅行愿望",
    description: "整理目的地、日期和偏好",
    status: "pending",
  },
  {
    id: "weather",
    label: "查看天气",
    description: "匹配晴雨与体感温度",
    status: "pending",
  },
  {
    id: "poi",
    label: "寻找心动地点",
    description: "筛选景点、餐厅和室内备选",
    status: "pending",
  },
  {
    id: "plan",
    label: "编排行程",
    description: "按上午、下午和晚间铺开节奏",
    status: "pending",
  },
  {
    id: "polish",
    label: "写情侣寄语",
    description: "给每个活动补一句温柔",
    status: "pending",
  },
];

const PHASE_STEP_INDEX: Record<string, number> = {
  parse_input: 0,
  fetch_weather: 1,
  search_poi: 2,
  search_food: 2,
  plan_itinerary: 3,
  budget_check: 3,
  adapt_weather: 3,
  add_couple_touch: 4,
  output_format: 4,
};

export interface StreamingDay {
  day_index: number;
  weather?: string;
  activities: Activity[];
}

interface TripStore {
  form: TripPlanRequest;
  plan: TripPlanResponse | null;
  planId: string | null;
  status: PlanStatus;
  currentStep: string;
  progress: PlanningStep[];
  error: string | null;
  streamingDays: StreamingDay[];
  budgetAlert: BudgetAlertEvent | null;
  weatherSwaps: WeatherSwapEvent[];
  coupleMessages: MessageEvent[];
  updateForm: (patch: Partial<TripPlanRequest>) => void;
  beginPlanning: () => Promise<void>;
  loadPlan: (planId: string) => Promise<boolean>;
  resetPlan: () => void;
}

function freshSteps(): PlanningStep[] {
  return PLANNING_STEPS.map((step) => ({ ...step, status: "pending" }));
}

function progressForPhase(phase: string): PlanningStep[] {
  const activeIndex = PHASE_STEP_INDEX[phase] ?? 0;

  return PLANNING_STEPS.map((step, index) => ({
    ...step,
    status:
      index < activeIndex
        ? "done"
        : index === activeIndex
          ? "active"
          : "pending",
  }));
}

export const useTripStore = create<TripStore>((set, get) => ({
  form: DEFAULT_FORM,
  plan: null,
  planId: null,
  status: "idle",
  currentStep: "",
  progress: freshSteps(),
  error: null,
  streamingDays: [],
  budgetAlert: null,
  weatherSwaps: [],
  coupleMessages: [],

  updateForm: (patch) => {
    set((state) => ({
      form: { ...state.form, ...patch },
    }));
  },

  beginPlanning: async () => {
    if (get().status === "planning") {
      return;
    }

    const request = get().form;

    set({
      status: "planning",
      plan: null,
      error: null,
      currentStep: "正在理解你们的旅行愿望",
      progress: progressForPhase("parse_input"),
      streamingDays: [],
      budgetAlert: null,
      weatherSwaps: [],
      coupleMessages: [],
    });

    try {
      const plan = await createPlan(request, {
        onStep: (event) => {
          set({
            currentStep: event.message || "正在规划行程",
            progress: progressForPhase(event.phase),
          });
        },
        onPartial: (payload: PartialEvent) => {
          set((state) => {
            const existing = state.streamingDays.find(
              (d) => d.day_index === payload.day_index,
            );
            if (existing) {
              return {};
            }
            return {
              streamingDays: [
                ...state.streamingDays,
                {
                  day_index: payload.day_index,
                  weather: payload.weather,
                  activities: payload.activities,
                },
              ],
            };
          });
        },
        onBudgetAlert: (payload: BudgetAlertEvent) => {
          set({ budgetAlert: payload });
        },
        onWeatherSwap: (payload: WeatherSwapEvent) => {
          set((state) => ({
            weatherSwaps: [...state.weatherSwaps, payload],
          }));
        },
        onMessage: (payload: MessageEvent) => {
          set((state) => ({
            coupleMessages: [...state.coupleMessages, payload],
          }));
        },
      });

      set({
        plan,
        planId: plan.plan_id,
        status: "ready",
        currentStep: "行程已就绪",
        progress: PLANNING_STEPS.map((step) => ({ ...step, status: "done" })),
      });
    } catch (error) {
      set({
        status: "error",
        error: error instanceof Error ? error.message : "行程生成失败，请稍后重试",
        currentStep: "规划失败",
        progress: freshSteps(),
      });
      throw error;
    }
  },

  loadPlan: async (planId: string) => {
    try {
      const result = await fetchPlan(planId);
      if (!result) {
        return false;
      }
      set({
        plan: result,
        planId: result.plan_id,
        status: "ready",
        currentStep: "行程已就绪",
        progress: PLANNING_STEPS.map((step) => ({ ...step, status: "done" })),
      });
      return true;
    } catch {
      return false;
    }
  },

  resetPlan: () => {
    set({
      form: DEFAULT_FORM,
      plan: null,
      planId: null,
      status: "idle",
      currentStep: "",
      progress: freshSteps(),
      error: null,
      streamingDays: [],
      budgetAlert: null,
      weatherSwaps: [],
      coupleMessages: [],
    });
  },
}));
