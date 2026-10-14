export type ChatIntent =
  | "greeting"
  | "question"
  | "planning_intent"
  | "planning_ready"
  | "modify_plan";

export interface Slots {
  destination?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  budget?: number | null;
  origin?: string | null;
  preferences?: string[] | null;
  pace?: string | null;
}

export interface ModifyPatch {
  destination?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  budget?: number | null;
  origin?: string | null;
  preferences?: string[] | null;
  pace?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatReply {
  session_id: string;
  reply: string;
  intent: ChatIntent;
  slots: Slots;
  ready: boolean;
  plan_request?: TripPlanRequestPayload | null;
  modify_patch?: ModifyPatch | null;
}

export interface TripPlanRequestPayload {
  origin: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget: number;
  preferences: string[];
  pace: string;
}

export type ChatStatus = "idle" | "sending" | "ready" | "error";
