import { TaskCard } from "../components/TaskCard";
import { listTasks } from "../lib/tasks";

export default async function Page() {
  const tasks = await listTasks();
  return <main>{tasks.map((task) => <TaskCard key={task.id} task={task} />)}</main>;
}
