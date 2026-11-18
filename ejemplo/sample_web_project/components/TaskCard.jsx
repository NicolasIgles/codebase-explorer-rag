export const TaskCard = ({ task }) => (
  <article>
    <h2>{task.title}</h2>
    <span>{task.done ? "Terminada" : "Pendiente"}</span>
  </article>
);
