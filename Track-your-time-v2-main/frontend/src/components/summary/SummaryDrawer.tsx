import { useState, useCallback } from 'react'
import { summaryApi } from '@/api/summary'
import { parseApiError } from '@/lib/utils'
import type { DaySummary } from '@/types/api'
import toast from 'react-hot-toast'
import { Sparkles, Loader2, ChevronDown } from 'lucide-react'
import { SummaryCard } from './SummaryCard'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'

interface SummaryDrawerProps {
  initialSummary?: DaySummary | null
}

export function SummaryDrawer({ initialSummary }: SummaryDrawerProps = {}) {
  const [generating, setGenerating] = useState(false)
  const [summary, setSummary] = useState<DaySummary | null>(initialSummary ?? null)
  const [summaryId, setSummaryId] = useState<string | null>(null)
  const [generatedAt, setGeneratedAt] = useState<Date | null>(initialSummary ? new Date() : null)
  const [open, setOpen] = useState(false)

  // ── Generate fresh summary ──────────────────────────────────────────────
  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const data = await summaryApi.trigger()
      setSummary(data)
      setGeneratedAt(new Date())
      setOpen(true)
      toast.success('Day-end summary generated!')
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setGenerating(false)
    }
  }

  // ── Save user edits ─────────────────────────────────────────────────────
  const handleSave = useCallback(
    async (editedBullets: string[]) => {
      if (!summaryId) {
        // For freshly triggered summaries that don't have a DB id yet,
        // we update local state. The next history fetch will pick up the id.
        setSummary((prev) =>
          prev
            ? { ...prev, edited_bullets: editedBullets, is_edited: true }
            : prev,
        )
        return
      }
      const updated = await summaryApi.updateSummary(summaryId, editedBullets)
      setSummary(updated)
    },
    [summaryId],
  )

  // ── Regenerate (revision, not reset) ────────────────────────────────────
  const handleRegenerate = useCallback(async () => {
    if (!summaryId) {
      toast.error('Save the summary first before regenerating')
      return
    }
    const updated = await summaryApi.regenerateSummary(summaryId)
    setSummary(updated)
  }, [summaryId])

  const now = new Date()
  const dateLabel = generatedAt
    ? format(generatedAt, 'EEEE, d MMMM')
    : format(now, 'EEEE, d MMMM')

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary tracking-tight">Summary</h2>
          <p className="text-sm text-text-secondary mt-0.5">
            Your day, distilled into what mattered and what's next.
          </p>
        </div>

        <button
          onClick={handleGenerate}
          className="btn-primary flex items-center justify-center gap-2 w-full sm:w-auto"
          disabled={generating}
        >
          {generating ? (
            <>
              <Loader2 className="animate-spin h-4 w-4" /> Generating...
            </>
          ) : (
            <>
              <Sparkles size={16} /> {summary ? 'Generate New' : 'Generate Summary'}
            </>
          )}
        </button>
      </div>

      {/* Generating skeleton */}
      {generating && (
        <div className="bg-[#111214] border border-white/[0.07] rounded-2xl px-5 py-4 space-y-3 animate-pulse">
          <div className="flex justify-between">
            <div className="h-4 bg-white/10 rounded w-36" />
            <div className="h-4 bg-white/5 rounded w-8" />
          </div>
          <div className="h-3 bg-white/5 rounded w-48" />
          <div className="space-y-2.5 pt-1">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-white/10 shrink-0" />
                <div className="h-3 bg-white/5 rounded" style={{ width: `${65 + Math.random() * 25}%` }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary card — expandable */}
      {summary && !generating && (
        <div>
          {/* Collapsed header — always visible */}
          <button
            onClick={() => setOpen((v) => !v)}
            className="w-full bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07] rounded-2xl px-5 py-3.5 flex items-center justify-between transition-colors duration-150"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-success shadow-[0_0_6px_2px_rgba(34,197,94,0.4)]" />
              <span className="text-sm font-semibold text-text-primary">{dateLabel}</span>
              {summary.is_edited && (
                <span className="text-[10px] text-text-muted bg-white/5 px-1.5 py-0.5 rounded">edited</span>
              )}
            </div>
            <ChevronDown
              size={16}
              className={cn(
                'text-text-muted transition-transform duration-200',
                open && 'rotate-180',
              )}
            />
          </button>

          {/* Expanded: the summary card */}
          {open && (
            <div className="-mt-2 relative z-10">
              <SummaryCard
                summaryId={summaryId ?? undefined}
                date={dateLabel}
                summary={summary}
                onSave={handleSave}
                onRegenerate={handleRegenerate}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
