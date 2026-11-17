export function formatTask(task) {
  return `${task.title}: ${task.done ? "done" : "pending"}`;
}
