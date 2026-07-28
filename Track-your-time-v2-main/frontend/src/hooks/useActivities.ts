import { useQuery } from '@tanstack/react-query'
import { activitiesApi } from '@/api/activities'
import type { ActivityListParams, ReminderActivity } from '@/types/api'

export const ACTIVITIES_KEY = ['activities'] as const

export function useActivities(params: ActivityListParams = {}) {
  return useQuery<ReminderActivity[]>({
    queryKey: [...ACTIVITIES_KEY, params],
    queryFn: () => activitiesApi.list(params),
    staleTime: 15_000,
  })
}
