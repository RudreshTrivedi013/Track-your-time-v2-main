import { Zap, AlertTriangle, MapPin } from 'lucide-react'
import type { DaySummary } from '@/types/api'

interface SummaryCardProps {
  date: string        // e.g. "Monday, 20 July"
  time: string        // e.g. "12:45 pm"
  subtitle: string    // e.g. "4 tasks completed, 11 notes created."
  summary: DaySummary
  isActive?: boolean  // green dot on the left edge
}

export function SummaryCard({ date, time, subtitle, summary, isActive }: SummaryCardProps) {
  return (
    <div className="relative flex">
      {/* Left accent dot */}
      <div className="flex flex-col items-center mr-3 pt-1">
        <div
          className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
            isActive ? 'bg-success shadow-[0_0_6px_2px_rgba(34,197,94,0.4)]' : 'bg-white/20'
          }`}
        />
        {/* Connector line */}
        <div className="w-px flex-1 bg-white/[0.06] mt-2" />
      </div>

      {/* Card */}
      <div className="flex-1 bg-[#111214] border border-white/[0.07] rounded-2xl px-5 py-4 space-y-3 mb-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm font-bold text-text-primary leading-tight">{date}</h3>
          <span className="text-xs text-text-muted shrink-0 mt-[1px]">{time}</span>
        </div>

        {/* Subtitle */}
        <p className="text-sm text-text-secondary leading-relaxed">{subtitle}</p>

        {/* Bullet points */}
        <div className="space-y-2 pt-1">
          {/* Highlight */}
          <div className="flex items-start gap-2.5">
            <Zap size={14} className="text-success shrink-0 mt-[2px]" />
            <p className="text-sm font-semibold text-text-primary leading-snug">{summary.highlight}</p>
          </div>

          {/* Concern */}
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={14} className="text-warning shrink-0 mt-[2px]" />
            <p className="text-sm font-semibold text-text-primary leading-snug">{summary.concern}</p>
          </div>

          {/* Tomorrow's suggestion */}
          <div className="flex items-start gap-2.5">
            <MapPin size={14} className="text-text-secondary shrink-0 mt-[2px]" />
            <p className="text-sm font-semibold text-text-primary leading-snug">{summary.tomorrow_suggestion}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
