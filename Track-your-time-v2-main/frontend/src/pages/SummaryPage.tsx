import { useSummaryStore } from '@/stores/summaryStore'
import { SummaryDrawer } from '@/components/summary/SummaryDrawer'
import { SummaryHistory } from '@/components/summary/SummaryHistory'

export default function SummaryPage() {
  const { pendingSummary } = useSummaryStore()

  return (
    <div className="max-w-2xl mx-auto space-y-6 px-1 sm:px-0">
      <SummaryDrawer initialSummary={pendingSummary} />
      <SummaryHistory />
    </div>
  )
}