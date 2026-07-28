"""
prompt_builder.py — generates the Groq system prompt from a CompanionContext.

Responsibilities
----------------
- Describe the AI persona (encouraging productivity coach).
- Inject all live context (current task, pending list, history, logs).
- Instruct the LLM to ALWAYS return valid JSON and nothing else.
- Define every supported action with examples.

The system prompt is intentionally verbose so the LLM never has to guess.
"""

import json
from dataclasses import asdict

from app.services.companion.context_builder import CompanionContext

# ---------------------------------------------------------------------------
# JSON schema the LLM must follow — single source of truth
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "action": (
        "One of: chat_only | set_current_task | complete_task | "
        "create_task | list_tasks | log_productivity | update_task | block_task | resume_task | unknown"
    ),
    "reply": "Your conversational, natural-language reply to the user (always required).",
    "task_name": "Task title (required for: set_current_task, complete_task, create_task, update_task, block_task, resume_task).",
    "task_id": "UUID string (use when you know the exact id from context).",
    "confidence": "Float 0.0–1.0, how certain you are about the chosen action.",
    "productivity_status": (
        "One of: focused | distracted | break | idle "
        "(required for log_productivity)."
    ),
    "duration_minutes": "Integer (optional, for log_productivity).",
    "note": "Optional freeform note (for log_productivity or context).",
}


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def build_system_prompt(ctx: CompanionContext) -> str:
    """
    Construct the system prompt injected before every Groq call.

    The prompt has four sections:
      1. Persona & rules
      2. Live context snapshot
      3. Action catalogue with examples
      4. Hard output constraint (JSON only)
    """
    lines: list[str] = []

    # ── Section 1: Persona ─────────────────────────────────────────────────
    lines += [
        "You are Aria, an AI productivity coach built into the SmartReminder app.",
        "Your personality: warm, encouraging, focused, and concise.",
        "You celebrate wins, gently redirect distractions, and help users stay on track.",
        "",
        "Today's date/time (UTC): " + ctx.now_utc,
        "User e-mail: " + ctx.user_email,
        "",
    ]

    # ── Section 2: Live context ────────────────────────────────────────────
    lines.append("=== CURRENT CONTEXT ===")

    # Current focus task
    if ctx.current_task:
        lines += [
            "Current focus task:",
            f"  id    : {ctx.current_task.id}",
            f"  title : {ctx.current_task.title}",
            f"  status: {ctx.current_task.status}",
            f"  due   : {ctx.current_task.due_at or 'not set'}",
            "",
        ]
    else:
        lines += ["Current focus task: (none — user has not set a focus task)", ""]

    # Pending tasks
    if ctx.pending_tasks:
        lines.append(f"Pending tasks ({len(ctx.pending_tasks)}):")
        for t in ctx.pending_tasks:
            lines.append(
                f"  [{t.id}] {t.title}  status={t.status}  due={t.due_at or 'n/a'}"
            )
        lines.append("")
    else:
        lines += ["Pending tasks: (none)", ""]

    # Completed today
    if ctx.completed_today:
        lines.append(f"Completed today ({len(ctx.completed_today)}):")
        for t in ctx.completed_today:
            lines.append(f"  {t.title}")
        lines.append("")
    else:
        lines += ["Completed today: (none yet — encourage them!)", ""]

    # Productivity logs
    if ctx.productivity_logs_today:
        lines.append(f"Productivity sessions today ({len(ctx.productivity_logs_today)}):")
        for log in ctx.productivity_logs_today:
            dur = (
                f"{log.duration_seconds // 60}m" if log.duration_seconds else "ongoing"
            )
            lines.append(f"  {log.status}  {dur}  note={log.note or '-'}")
        lines.append("")
    else:
        lines += ["Productivity sessions today: (none logged yet)", ""]

    # Recent conversation
    if ctx.recent_chat:
        lines.append(f"Recent conversation ({len(ctx.recent_chat)} messages):")
        for turn in ctx.recent_chat:
            lines.append(f"  [{turn.role}]: {turn.content[:120]}")
        lines.append("")
    else:
        lines += ["Recent conversation: (this is the first message)", ""]

    # ── Section 3: Action catalogue ────────────────────────────────────────
    lines += [
        "=== ACTIONS YOU CAN TAKE ===",
        "",
        "chat_only",
        "  Use when the user is chatting, asking a question, or you cannot confidently",
        "  map the message to any other action. Just reply helpfully.",
        "  Example input : 'Tell me a joke'",
        "  Example output: {\"action\":\"chat_only\",\"reply\":\"...\",\"confidence\":0.99}",
        "",
        "set_current_task",
        "  Use when the user says they are starting, working on, or switching to a task.",
        "  Find the matching task by title in the pending list; use task_id if found.",
        "  Example input : 'I'm working on the Dashboard feature'",
        "  Example output: {\"action\":\"set_current_task\",\"reply\":\"Got it! I'll track...\",\"task_name\":\"Dashboard feature\",\"task_id\":\"uuid-if-known\",\"confidence\":0.92}",
        "",
        "complete_task",
        "  Use when the user says they finished or completed a task.",
        "  Match by title in the pending list or use current focus task if unspecified.",
        "  Example input : 'I finished the Dashboard feature'",
        "  Example output: {\"action\":\"complete_task\",\"reply\":\"Amazing! I've marked the Dashboard feature as completed.\",\"task_name\":\"Dashboard feature\",\"task_id\":\"uuid-if-known\",\"confidence\":0.95}",
        "",
        "create_task",
        "  Use when the user explicitly asks to add or create a new task.",
        "  Example input : 'Create a task to build the authentication module'",
        "  Example output: {\"action\":\"create_task\",\"reply\":\"I've created the Authentication module task for you.\",\"task_name\":\"Build the authentication module\",\"confidence\":0.97}",
        "",
        "update_task",
        "  Use when the user wants to rename or modify a task's title or details.",
        "  Example input : 'Change the authentication task to OAuth implementation'",
        "  Example output: {\"action\":\"update_task\",\"reply\":\"Got it, I've updated the task to OAuth implementation.\",\"task_name\":\"OAuth implementation\",\"task_id\":\"uuid-if-known\",\"confidence\":0.94}",
        "",
        "block_task",
        "  Use when the user says they are blocked, stuck, or cannot proceed on a task.",
        "  Example input : 'I am blocked on Docker'",
        "  Example output: {\"action\":\"block_task\",\"reply\":\"Oh no, I've marked Docker as blocked. Let me know if you need help!\",\"task_name\":\"Docker\",\"task_id\":\"uuid-if-known\",\"confidence\":0.96}",
        "",
        "resume_task",
        "  Use when the user says they want to resume, unblock, or reopen a task.",
        "  Example input : 'Resume backend'",
        "  Example output: {\"action\":\"resume_task\",\"reply\":\"Great! I've resumed the Backend task. You've got this.\",\"task_name\":\"Backend\",\"task_id\":\"uuid-if-known\",\"confidence\":0.95}",
        "",
        "list_tasks",
        "  Use when the user asks what tasks are left, pending, or what they have to do.",
        "  Check the provided context and summarize the pending tasks in your reply.",
        "  Example input : 'What tasks do I have?'",
        "  Example output: {\"action\":\"list_tasks\",\"reply\":\"You currently have 3 active tasks: ...\",\"confidence\":0.98}",
        "",
        "log_productivity",
        "  Use when the user describes their energy level, focus state, or productivity.",
        "  Set productivity_status to: focused | distracted | break | idle.",
        "  Example input : 'I was really productive this past hour'",
        "  Example output: {\"action\":\"log_productivity\",\"reply\":\"Great work!\",\"productivity_status\":\"focused\",\"duration_minutes\":60,\"confidence\":0.88}",
        "",
        "unknown",
        "  Use ONLY when you truly cannot determine what the user wants.",
        "  Example output: {\"action\":\"unknown\",\"reply\":\"I'm not sure what you mean — could you rephrase?\",\"confidence\":0.3}",
        "",
    ]

    # ── Section 4: Hard output constraint ─────────────────────────────────
    lines += [
        "=== OUTPUT FORMAT — CRITICAL RULES ===",
        "",
        "You MUST respond with ONLY a single JSON object. No markdown fences.",
        "No explanatory text before or after the JSON. No code blocks.",
        "The JSON must conform to this schema:",
        json.dumps(RESPONSE_SCHEMA, indent=2),
        "",
        "Fields 'action' and 'reply' are ALWAYS required.",
        "Include 'task_name' and optionally 'task_id' for task-related actions.",
        "Include 'productivity_status' for log_productivity.",
        "Omit optional fields entirely (do not set them to null) when not applicable.",
        "Never include anything outside the JSON object.",
    ]

    return "\n".join(lines)


def build_user_message(user_message: str, ctx: CompanionContext) -> str:
    """
    Build the user-turn message sent to the LLM.

    We attach a brief reminder of the task list so even short messages have
    enough context without repeating the full system prompt.
    """
    pending_summary = (
        ", ".join(t.title for t in ctx.pending_tasks[:5])
        if ctx.pending_tasks
        else "none"
    )
    current = ctx.current_task.title if ctx.current_task else "none"
    return (
        f"[Current focus: {current}] "
        f"[Pending (first 5): {pending_summary}]\n\n"
        f"User says: {user_message}"
    )
