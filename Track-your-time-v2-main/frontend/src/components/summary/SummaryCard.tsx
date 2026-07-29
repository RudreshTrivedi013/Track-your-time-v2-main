import { useState, useRef, useCallback } from 'react'
import { Copy, Check, RefreshCw, Loader2 } from 'lucide-react'
import type { DaySummary } from '@/types/api'
import toast from 'react-hot-toast'

interface SummaryCardProps {
  date: string
  summary: DaySummary
  /** Called when the user saves an edit (blur). */
  onSave?: (editedBullets: string[]) => Promise<void>
  /** Called when the user taps the regenerate icon. */
  onRegenerate?: () => Promise<void>
}

export function SummaryCard({
  date,
  summary,
  onSave,
  onRegenerate,
}: SummaryCardProps) {
  // Which bullets to display: edited if available, else generated
  const displayBullets = summary.edited_bullets ?? summary.generated_bullets

  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // ── Copy to clipboard ───────────────────────────────────────────────────
  const handleCopy = useCallback(async () => {
    const text = displayBullets.map((b) => `• ${b}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Failed to copy')
    }
  }, [displayBullets])

  // ── Enter edit mode ─────────────────────────────────────────────────────
  const startEditing = useCallback(() => {
    if (regenerating || saving) return
    setEditText(displayBullets.join('\n'))
    setEditing(true)
    // Auto-focus after React renders the textarea
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
      // Move cursor to end
      const len = textareaRef.current?.value.length ?? 0
      textareaRef.current?.setSelectionRange(len, len)
    })
  }, [displayBullets, regenerating, saving])

  // ── Save on blur ────────────────────────────────────────────────────────
  const handleBlur = useCallback(async () => {
    const lines = editText
      .split('\n')
      .map((l) => l.replace(/^[•\-*]\s*/, '').trim()) // strip leading bullet chars
      .filter(Boolean)

    if (lines.length === 0) {
      // Empty edit — cancel
      setEditing(false)
      return
    }

    // Check if anything actually changed
    const unchanged =
      lines.length === displayBullets.length &&
      lines.every((l, i) => l === displayBullets[i])
    if (unchanged) {
      setEditing(false)
      return
    }

    setSaving(true)
    try {
      await onSave?.(lines)
      setEditing(false)
    } catch {
      toast.error('Failed to save edits')
    } finally {
      setSaving(false)
    }
  }, [editText, displayBullets, onSave])

  // ── Regenerate (only when edited) ───────────────────────────────────────
  const handleRegenerate = useCallback(async () => {
    if (!summary.is_edited || regenerating) return
    setRegenerating(true)
    try {
      await onRegenerate?.()
    } catch {
      toast.error('Regeneration failed')
    } finally {
      setRegenerating(false)
    }
  }, [summary.is_edited, regenerating, onRegenerate])

  // Auto-resize textarea
  const handleTextareaInput = useCallback(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = `${ta.scrollHeight}px`
    }
  }, [])

  return (
    <div className="bg-[#111214] border border-white/[0.07] rounded-2xl px-5 py-4 space-y-3">
      {/* Header: date + copy icon */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-text-primary leading-tight">
            {date}
          </h3>
          {!editing && (
            <p className="text-xs text-text-muted mt-0.5">
              Tap the text to edit
            </p>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Regenerate icon — only when edited */}
          {summary.is_edited && !editing && (
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors disabled:opacity-50"
              title="Regenerate (refine your edit)"
              aria-label="Regenerate summary"
            >
              {regenerating ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <RefreshCw size={15} />
              )}
            </button>
          )}

          {/* Copy icon */}
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
            title="Copy summary"
            aria-label="Copy summary to clipboard"
          >
            {copied ? (
              <Check size={15} className="text-success" />
            ) : (
              <Copy size={15} />
            )}
          </button>
        </div>
      </div>

      {/* Bullets / Edit textarea */}
      {editing ? (
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={editText}
            onChange={(e) => {
              setEditText(e.target.value)
              handleTextareaInput()
            }}
            onBlur={handleBlur}
            className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3 text-sm text-text-primary leading-relaxed resize-none focus:outline-none focus:border-white/25 transition-colors"
            rows={Math.max(displayBullets.length, 3)}
            style={{ minHeight: '100px' }}
          />
          {saving && (
            <div className="absolute top-2 right-2">
              <Loader2 size={14} className="animate-spin text-text-muted" />
            </div>
          )}
        </div>
      ) : (
        <ul
          className="space-y-2.5 cursor-text"
          onClick={startEditing}
        >
          {displayBullets.map((bullet, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <span className="text-text-muted mt-[7px] shrink-0 text-[6px]">●</span>
              <p className="text-sm text-text-primary leading-relaxed">{bullet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
