/**
 * AI Companion Types mapped to backend Pydantic schemas.
 */

export type MessageRole = 'user' | 'assistant' | 'system';
export type ProductivityStatus = 'focused' | 'distracted' | 'break' | 'idle';

export interface HourlyCheckinReminder {
  id: string;
  user_id: string;
  scheduled_time: string;
  status: 'pending' | 'completed' | 'missed';
  response_id: string | null;
  created_at: string;
}

// --- Chat ---

export interface ChatRequest {
  content: string;
  task_id: string | null;
}

export interface ChatMessage {
  id: string;
  user_id: string;
  task_id: string | null;
  role: MessageRole;
  content: string;
  token_count: number | null;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  total: number;
}

// --- Check-in / Productivity Logs ---

export interface ProductivityLogCreate {
  task_id?: string | null;
  reminder_id?: string | null;
  status: ProductivityStatus;
  start_at?: string | null;
  end_at?: string | null;
  duration_seconds?: number | null;
  note?: string | null;
  transcript?: string | null;
  source?: 'voice' | 'text' | null;
}

export interface ProductivityLog {
  id: string;
  user_id: string;
  task_id: string | null;
  status: ProductivityStatus;
  start_at: string;
  end_at: string | null;
  duration_seconds: number | null;
  note: string | null;
}

// --- Current Task ---

export interface CurrentTaskSet {
  task_id?: string | null;
  context_note?: string | null;
  is_active?: boolean;
}

export interface CurrentTask {
  user_id: string;
  task_id: string | null;
  context_note: string | null;
  is_active: boolean;
  started_at: string | null;
  updated_at: string;
}

// --- Summary ---

export interface ProductivityStats {
  today_productive_hours: number;
  focus_percentage: number;
  total_sessions_today: number;
  missed_checkins: number;
  current_streak: number;
  longest_streak: number;
}

export interface ProductivitySummary {
  user_id: string;
  period_days: number;
  total_sessions_all_time: number;
  mock: boolean;
  note?: string;
  stats: ProductivityStats;
  generated_at: string;
}

// --- Error Handling ---

export interface APIError extends Error {
  status?: number;
  data?: any;
  isNetworkError?: boolean;
}
