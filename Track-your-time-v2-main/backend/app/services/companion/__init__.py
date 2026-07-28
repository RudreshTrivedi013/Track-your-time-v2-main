"""
AI Productivity Companion — service layer.

Sub-modules
-----------
context_builder  Collects all user context (tasks, logs, chat history).
prompt_builder   Generates the system prompt for Groq.
intent_parser    Safely parses the LLM's JSON response.
task_actions     Executes DB side-effects for each intent action.
chat_service     Orchestrates the full request→response pipeline.
"""
