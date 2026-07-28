import { useState, useEffect } from 'react'
import { summaryApi } from '@/api/summary'
import { parseApiError } from '@/lib/utils'
import type { DailySummaryOut } from '@/types/api'
import toast from 'react-hot-toast'
import { ChevronDown, Loader2, Zap, AlertTriangle, MapPin } from 'lucide-react'
import { format, parseISO } from 'date-fns'

// ── Single collapsible past-summary row ─────────────────────────────────────
function PastSummaryRow({ s }: { s: DailySummaryOut }) {
  const [open, setOpen] = useState(false)

  const dateObj = parseISO(s.date)
  const dateLabel = format(dateObj, 'EEEE, d MMMM')       // "Sunday, 19 July"
  const timeLabel = format(new Date(s.created_at), 'h:mm aa')

  return (
    <div className="relative flex">
      {/* Left dot + connector */}
      <div className="flex flex-col items-center mr-3 pt-1">
        <div className="w-2.5 h-2.5 rounded-full bg-white/20 mt-1 shrink-0" />
        <div className="w-px flex-1 bg-white/[0.06] mt-2" />
      </div>

      {/* Card */}
      <div className="flex-1 mb-3">
        {/* Collapsed header — always visible */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="w-full bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07] rounded-2xl px-5 py-3.5 flex items-center justify-between transition-colors duration-150"
        >
          <span className="text-sm font-semibold text-text-primary">{dateLabel}</span>
          <ChevronDown
            size={16}
            className={`text-text-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </button>

        {/* Expanded content */}
        {open && (
          <div className="bg-[#111214] border border-t-0 border-white/[0.07] rounded-b-2xl -mt-2 pt-5 pb-4 px-5 space-y-3">
            {/* Time */}
            <p className="text-xs text-text-muted">{timeLabel}</p>

            {/* Overview sentence */}
            <p className="text-sm text-text-secondary leading-relaxed">{s.content.summary}</p>

            {/* Bullet points */}
            <div className="space-y-2 pt-1">
              <div className="flex items-start gap-2.5">
                <Zap size={14} className="text-success shrink-0 mt-[2px]" />
                <p className="text-sm font-semibold text-text-primary leading-snug">{s.content.highlight}</p>
              </div>
              <div className="flex items-start gap-2.5">
                <AlertTriangle size={14} className="text-warning shrink-0 mt-[2px]" />
                <p className="text-sm font-semibold text-text-primary leading-snug">{s.content.concern}</p>
              </div>
              <div className="flex items-start gap-2.5">
                <MapPin size={14} className="text-text-secondary shrink-0 mt-[2px]" />
                <p className="text-sm font-semibold text-text-primary leading-snug">{s.content.tomorrow_suggestion}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── History list ─────────────────────────────────────────────────────────────
export function SummaryHistory() {
  const [summaries, setSummaries] = useState<DailySummaryOut[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const LIMIT = 10

  const fetchHistory = async (currentOffset: number, append = false) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const data = await summaryApi.getHistory(LIMIT, currentOffset)
      if (append) {
        setSummaries((prev) => [...prev, ...data.summaries])
      } else {
        setSummaries(data.summaries)
      }
      setTotal(data.total)
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      if (append) setLoadingMore(false)
      else setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory(0)
  }, [])

  const handleLoadMore = () => {
    const nextOffset = offset + LIMIT
    setOffset(nextOffset)
    fetchHistory(nextOffset, true)
  }

  if (loading && summaries.length === 0) {
    return (
      <div className="space-y-3">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="flex">
            <div className="flex flex-col items-center mr-3 pt-1">
              <div className="w-2.5 h-2.5 rounded-full bg-white/10 mt-1" />
            </div>
            <div className="flex-1 h-12 rounded-2xl bg-white/[0.04] animate-pulse mb-3" />
          </div>
        ))}
      </div>
    )
  }

  if (summaries.length === 0) {
    return (
      <p className="text-sm text-text-muted text-center py-6">No past summaries yet.</p>
    )
  }

  return (
    <div className="space-y-0">
      {summaries.map((s) => (
        <PastSummaryRow key={s.id} s={s} />
      ))}

      {summaries.length < total && (
        <div className="pt-2 flex justify-center">
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="btn-secondary py-2 px-6 flex items-center gap-2"
          >
            {loadingMore && <Loader2 className="animate-spin h-4 w-4" />}
            {loadingMore ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  )
}
