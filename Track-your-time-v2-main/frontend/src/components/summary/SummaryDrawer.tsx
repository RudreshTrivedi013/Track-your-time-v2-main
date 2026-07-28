import { useState } from 'react'
import { summaryApi } from '@/api/summary'
import { parseApiError } from '@/lib/utils'
import type { DaySummary } from '@/types/api'
import toast from 'react-hot-toast'
import { Sparkles, Loader2 } from 'lucide-react'
import { SummaryCard } from './SummaryCard'
import { format } from 'date-fns'

interface SummaryDrawerProps {
  initialSummary?: DaySummary | null
}

export function SummaryDrawer({ initialSummary }: SummaryDrawerProps = {}) {
  const [generating, setGenerating] = useState(false)
  const [summary, setSummary] = useState<DaySummary | null>(initialSummary ?? null)
  const [generatedAt, setGeneratedAt] = useState<Date | null>(initialSummary ? new Date() : null)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const data = await summaryApi.trigger()
      setSummary(data)
      setGeneratedAt(new Date())
      toast.success('Day-end summary generated!')
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setGenerating(false)
    }
  }

  const now = new Date()
  const dateLabel = format(now, 'EEEE, d MMMM')   // e.g. "Monday, 20 July"
  const timeLabel = format(now, 'h:mm aa')          // e.g. "6:01 pm"

  return (
    <div className="space-y-4">
      {/* Header row: stacks on mobile so the CTA gets its own full-width row
          instead of squeezing onto the title's line. */}
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
              <Sparkles size={16} /> {summary ? 'Regenerate' : 'Generate Summary'}
            </>
          )}
        </button>
      </div>

      {/* Generating skeleton */}
      {generating && (
        <div className="flex">
          <div className="flex flex-col items-center mr-3 pt-1">
            <div className="w-2.5 h-2.5 rounded-full bg-white/20 mt-1 animate-pulse" />
            <div className="w-px flex-1 bg-white/[0.06] mt-2" />
          </div>
          <div className="flex-1 bg-[#111214] border border-white/[0.07] rounded-2xl px-5 py-4 space-y-3 mb-3 animate-pulse">
            <div className="flex justify-between">
              <div className="h-4 bg-white/10 rounded w-36" />
              <div className="h-3 bg-white/5 rounded w-16" />
            </div>
            <div className="h-3 bg-white/5 rounded w-64" />
            <div className="space-y-2 pt-1">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <div className="w-3.5 h-3.5 rounded-full bg-white/10 shrink-0" />
                  <div className="h-3 bg-white/5 rounded w-4/5" />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Summary card */}
      {summary && !generating && (
        <SummaryCard
          date={generatedAt ? format(generatedAt, 'EEEE, d MMMM') : dateLabel}
          time={generatedAt ? format(generatedAt, 'h:mm aa') : timeLabel}
          subtitle={summary.summary}
          summary={summary}
          isActive
        />
      )}
    </div>
  )
}
