import api from './axios'
import type { Task, TaskCreateRequest, TaskUpdateRequest, TaskActionRequest } from '@/types/api'

export const tasksApi = {
  list: (skip = 0, limit = 50) =>
    api.get<Task[]>('/tasks', { params: { skip, limit } }).then((r) => r.data),

  create: (data: TaskCreateRequest) =>
    api.post<Task>('/tasks', data).then((r) => r.data),

  update: (id: string, data: TaskUpdateRequest) =>
    api.patch<Task>(`/tasks/${id}`, data).then((r) => r.data),

  recent: (limit = 1) =>
    api.get<Task[]>('/tasks/recent', { params: { limit } }).then((r) => r.data),

  delete: (id: string) => api.delete(`/tasks/${id}`),

  action: (id: string, data: TaskActionRequest) =>
    api.post<Task>(`/tasks/${id}/action`, data).then((r) => r.data),
}
