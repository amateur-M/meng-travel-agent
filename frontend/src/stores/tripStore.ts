import { create } from "zustand";
import { createMockPlan } from "../mocks/trip";
import type {
  PlanningStep,
  PlanStatus,
  TripPlanRequest,
  TripPlanResponse,
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

const MOCK_STEPS: PlanningStep[] = [
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

interface TripStore {
  form: TripPlanRequest;
  plan: TripPlanResponse | null;
  status: PlanStatus;
  currentStep: string;
  progress: PlanningStep[];
  error: string | null;
  updateForm: (patch: Partial<TripPlanRequest>) => void;
  beginPlanning: () => Promise<void>;
  resetPlan: () => void;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export const useTripStore = create<TripStore>((set, get) => ({
  form: DEFAULT_FORM,
  plan: null,
  status: "idle",
  currentStep: "",
  progress: MOCK_STEPS.map((step) => ({ ...step, status: "pending" })),
  error: null,

  updateForm: (patch) => {
    set((state) => ({
      form: { ...state.form, ...patch },
    }));
  },

  beginPlanning: async () => {
    if (get().status === "planning") {
      return;
    }

    set({
      status: "planning",
      plan: null,
      error: null,
      currentStep: "正在理解你们的旅行愿望",
      progress: MOCK_STEPS.map((step, index) => ({
        ...step,
        status: index === 0 ? "active" : "pending",
      })),
    });

    for (let index = 0; index < MOCK_STEPS.length; index += 1) {
      await wait(560);

      set({
        currentStep: MOCK_STEPS[index].description,
        progress: MOCK_STEPS.map((step, stepIndex) => ({
          ...step,
          status:
            stepIndex < index
              ? "done"
              : stepIndex === index
                ? "active"
                : "pending",
        })),
      });
    }

    await wait(360);

    set({
      plan: createMockPlan(get().form),
      status: "ready",
      currentStep: "行程已就绪",
      progress: MOCK_STEPS.map((step) => ({ ...step, status: "done" })),
    });
  },

  resetPlan: () => {
    set({
      form: DEFAULT_FORM,
      plan: null,
      status: "idle",
      currentStep: "",
      progress: MOCK_STEPS.map((step) => ({ ...step, status: "pending" })),
      error: null,
    });
  },
}));
