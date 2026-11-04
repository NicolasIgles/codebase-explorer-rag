export interface Task {
  id: string;
  title: string;
  done: boolean;
}

const tasks: Task[] = [];

export async function listTasks(): Promise<Task[]> {
  return tasks;
}

export async function saveTask(task: Task): Promise<void> {
  tasks.push(task);
}
