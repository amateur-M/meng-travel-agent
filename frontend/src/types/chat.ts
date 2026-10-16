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
  /** Server-side turn id; lets a retry reuse it so the turn is not duplicated. */
  messageId?: string | null;
  createdAt?: string | null;
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

// ── Conversation persistence (V3/P1–P3) ──────────────────────────────

export interface SessionSummary {
  session_id: string;
  title?: string | null;
  updated_at?: string | null;
  last_plan_id?: string | null;
  message_count: number;
  preview: string;
}

export interface SessionDetail {
  session_id: string;
  title?: string | null;
  summary?: string | null;
  slots: Slots;
  plan_request?: TripPlanRequestPayload | null;
  last_plan_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  message_count: number;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  message_id?: string | null;
}

export interface RecallTrip {
  plan_id: string;
  destination?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: string | null;
}

export interface RecallFeedback {
  activity_name: string;
  up: number;
  down: number;
}

export interface Recall {
  trips: RecallTrip[];
  feedback: RecallFeedback[];
}

export interface ProfilePatch {
  origin?: string;
  pace?: string;
  preferences?: string[];
  avoid?: string[];
  budget?: number;
}
