export type TaskStatus = 'pending' | 'in_progress' | 'done' | 'snoozed' | 'blocked'
export type Recurrence = 'none' | 'interval' | 'daily' | 'weekly'
export type TaskSource = 'voice' | 'text'

export interface LoginRequest {
  email: string
  password: string
}

export interface SignupRequest {
  email: string
  password: string
  timezone?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  email: string
  timezone: string
  quiet_hours_start: string | null
  quiet_hours_end: string | null
  working_hours_start: string
  working_hours_end: string
  checkin_interval_minutes: number
  daily_summary_enabled: boolean
  reminders_enabled: boolean
  checkin_enabled: boolean
}

export interface UserUpdate {
  working_hours_start?: string | null
  working_hours_end?: string | null
  checkin_interval_minutes?: number | null
  daily_summary_enabled?: boolean | null
  reminders_enabled?: boolean | null
  checkin_enabled?: boolean | null
  timezone?: string | null
}

export interface TaskNoteIn {
  text: string
  done?: boolean
  order_index?: number
}

export interface TaskNoteOut {
  id: string
  text: string
  done: boolean
  order_index: number
}

export interface Task {
  id: string
  user_id: string
  title: string
  status: TaskStatus
  recurrence: Recurrence
  due_at: string | null
  anchor_time: string | null
  interval_minutes: number | null
  next_due_at: string | null
  snoozed_until: string | null
  snoozed_count_today: number
  snoozed_count_total: number
  category: string | null
  source: TaskSource
  created_at: string
  updated_at: string
  notes: TaskNoteOut[]
}

export interface TaskCreateRequest {
  title: string
  recurrence?: Recurrence
  due_at?: string | null
  interval_minutes?: number | null
  category?: string | null
  source?: TaskSource
  notes?: TaskNoteIn[]
}

export interface TaskUpdateRequest {
  title?: string | null
  status?: TaskStatus | null
  recurrence?: Recurrence | null
  due_at?: string | null
  interval_minutes?: number | null
  category?: string | null
}

export interface TaskActionRequest {
  action: string
  client_timestamp: string
  snooze_minutes?: number | null
}

export interface ParsedNote {
  text: string
}

export interface ParsedTask {
  title: string
  due_date: string | null
  due_time: string | null
  recurrence: Recurrence
  interval_minutes: number | null
  notes: ParsedNote[]
  ambiguous_fields: string[]
}

export interface ParsedVoiceResult {
  tasks: ParsedTask[]
}

export interface Device {
  id: string
  is_primary: boolean
  last_active_at: string
  push_enabled: boolean
}

export interface DaySummary {
  summary: string
  highlight: string
  concern: string
  tomorrow_suggestion: string
}

export interface TaskNote{
 detail: string | Array<{ msg: string; loc: string[]; type: string }>
}

// ── Reminder Activity (response flow) ─────────────────────────────────────
export type ActivityType =
  | 'created'
  | 'started'
  | 'working'
  | 'updated'
  | 'completed'
  | 'blocked'
  | 'resumed'
  | 'snoozed'
  | 'deleted'
  | 'reminder_response'
  | 'hourly_checkin'
  | 'voice_update'
  | 'text_update'
  | 'companion_action'
  | 'status_update'
export type ActivitySource =
  | 'voice'
  | 'text'
  | 'task'
  | 'reminder'
  | 'checkin'
  | 'companion'
  | 'system'
export interface ReminderActivity {
  id: string
  user_id: string
  task_id: string | null
  activity_type: ActivityType
  task_title: string
  optional_notes: string | null
  source: ActivitySource
  timestamp: string
  metadata: Record<string, unknown> | null
}
export interface ActivitySubmitRequest {
  text: string
  source: 'voice' | 'text'
  task_id?: string | null
}

export interface ActivityListParams {
  today?: boolean
  date?: string
  limit?: number
  activity_type?: ActivityType
  source?: ActivitySource
}

export interface DailySummaryOut {
  id: string
  user_id: string
  date: string
  content: DaySummary
  created_at: string
}

export interface SummaryHistoryOut {
  summaries: DailySummaryOut[]
  total: number
}
