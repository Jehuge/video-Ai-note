import { create } from 'zustand'

export interface Task {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'transcribing' | 'summarizing' | 'completed' | 'failed'
  markdown?: string
  createdAt?: string
}

interface TaskStore {
  tasks: Task[]
  currentTaskId: string | null
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  setCurrentTask: (id: string | null) => void
  loadTasks: (tasks: Task[]) => void
  removeTask: (id: string) => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  currentTaskId: null,
  
  addTask: (task) =>
    set((state) => ({
      tasks: [task, ...state.tasks],
      currentTaskId: task.id,
    })),
  
  updateTask: (id, updates) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id ? { ...task, ...updates } : task
      ),
    })),
  
  setCurrentTask: (id) =>
    set({ currentTaskId: id }),
  
  loadTasks: (tasks) =>
    set({ tasks }),
  
  removeTask: (id) =>
    set((state) => {
      const newTasks = state.tasks.filter((task) => task.id !== id)
      // 如果删除的是当前选中的任务，清除选中状态
      const newCurrentTaskId = state.currentTaskId === id ? null : state.currentTaskId
      return {
        tasks: newTasks,
        currentTaskId: newCurrentTaskId,
      }
    }),
}))

