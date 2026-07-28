import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi } from '@/api/tasks'
import { ACTIVITIES_KEY } from '@/hooks/useActivities'
import type { Task, TaskCreateRequest, TaskUpdateRequest, TaskActionRequest } from '@/types/api'
import toast from 'react-hot-toast'
import { parseApiError } from '@/lib/utils'
import { markSelfAction } from '@/lib/selfActionTracker'

export const TASKS_KEY = ['tasks'] as const

export function useTasks() {
  return useQuery<Task[]>({
    queryKey: TASKS_KEY,
    queryFn: () => tasksApi.list(0, 100),
    staleTime: 30_000,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TaskCreateRequest) => tasksApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TASKS_KEY })
      qc.invalidateQueries({ queryKey: ACTIVITIES_KEY })
      toast.success('Task created!')
    },
    onError: (err: unknown) => toast.error(parseApiError(err)),
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskUpdateRequest }) =>
      tasksApi.update(id, data),
    onMutate: ({ id }: { id: string; data: TaskUpdateRequest }) => markSelfAction(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TASKS_KEY })
      qc.invalidateQueries({ queryKey: ACTIVITIES_KEY })
      toast.success('Task updated!')
    },
    onError: (err: unknown) => toast.error(parseApiError(err)),
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => tasksApi.delete(id),
    onMutate: (id: string) => markSelfAction(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TASKS_KEY })
      qc.invalidateQueries({ queryKey: ACTIVITIES_KEY })
      toast.success('Task deleted')
    },
    onError: (err: unknown) => toast.error(parseApiError(err)),
  })
}

// Action -> optimistic status, applied to the cache immediately so Done/
// Snooze/Mute read as instant even though the server round trip (plus the
// fire-and-forget push-cancel it kicks off) can lag on a slow connection.
const OPTIMISTIC_STATUS: Record<string, Task['status']> = {
  done: 'done',
  block: 'blocked',
  reopen: 'pending',
  snooze: 'snoozed',
}

export function useTaskAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskActionRequest }) =>
      tasksApi.action(id, data),
    onMutate: async ({ id, data }: { id: string; data: TaskActionRequest }) => {
      markSelfAction(id)
      await qc.cancelQueries({ queryKey: TASKS_KEY })
      const previousTasks = qc.getQueryData<Task[]>(TASKS_KEY)
      const nextStatus = OPTIMISTIC_STATUS[data.action]

      if (nextStatus) {
        qc.setQueryData<Task[]>(TASKS_KEY, (tasks) =>
          tasks?.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: nextStatus,
                  snoozed_until:
                    data.action === 'snooze'
                      ? new Date(Date.now() + (data.snooze_minutes ?? 10) * 60_000).toISOString()
                      : t.snoozed_until,
                }
              : t,
          ),
        )
      }

      return { previousTasks }
    },
    onError: (err: unknown, _variables, context) => {
      if (context?.previousTasks) qc.setQueryData(TASKS_KEY, context.previousTasks)
      toast.error(parseApiError(err))
    },
    onSuccess: (_data: any, variables: { id: string; data: TaskActionRequest }) => {
      // No emoji: cross-platform emoji rendering is the fastest way to make a
      // restrained dark UI look cheap. "block" is surfaced as Mute.
      const labels: Record<string, string> = {
        done: 'Marked as done',
        start: 'Started',
        block: 'Reminders muted',
        reopen: 'Reopened',
        snooze: 'Snoozed',
      }
      toast.success(labels[variables.data.action] ?? 'Updated')
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: TASKS_KEY })
      qc.invalidateQueries({ queryKey: ACTIVITIES_KEY })
    },
  })
}
