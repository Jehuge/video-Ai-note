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
}))

