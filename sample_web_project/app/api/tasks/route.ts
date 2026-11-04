import { listTasks, saveTask } from "../../../lib/tasks";

export async function GET() {
  return Response.json(await listTasks());
}

export async function POST(request: Request) {
  const task = await request.json();
  await saveTask(task);
  return Response.json(task, { status: 201 });
}
