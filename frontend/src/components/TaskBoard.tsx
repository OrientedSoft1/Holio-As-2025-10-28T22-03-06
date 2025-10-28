import React, { useState, useEffect } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
  DragOverEvent,
} from '@dnd-kit/core';
import { Plus, Trash2, GripVertical } from 'lucide-react';
import { apiClient } from 'app';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { TaskStatus } from 'types';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { cn } from '@/lib/utils';

interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

interface Props {
  projectId: string;
}

interface Column {
  id: TaskStatus;
  title: string;
  tasks: Task[];
}

export const TaskBoard = ({ projectId }: Props) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [showNewTaskForm, setShowNewTaskForm] = useState<TaskStatus | null>(null);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  useEffect(() => {
    loadTasks();
  }, [projectId]);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const response = await apiClient.list_tasks({ projectId });
      const data = await response.json();
      if (data.success) {
        setTasks(data.tasks || []);
      }
    } catch (error) {
      console.error('Failed to load tasks:', error);
      toast.error('Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  const columns: Column[] = [
    {
      id: TaskStatus.Todo,
      title: 'To Do',
      tasks: tasks.filter((t) => t.status === TaskStatus.Todo),
    },
    {
      id: TaskStatus.Inprogress,
      title: 'In Progress',
      tasks: tasks.filter((t) => t.status === TaskStatus.Inprogress),
    },
    {
      id: TaskStatus.Done,
      title: 'Done',
      tasks: tasks.filter((t) => t.status === TaskStatus.Done),
    },
  ];

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { over } = event;
    setOverId(over ? (over.id as string) : null);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    setOverId(null);

    if (!over) return;

    const taskId = active.id as string;
    const overId = over.id as string;

    // Check if we're over a column (TaskStatus) or a task
    let newStatus: TaskStatus | null = null;
    if (Object.values(TaskStatus).includes(overId as TaskStatus)) {
      newStatus = overId as TaskStatus;
    } else {
      // We're over a task, find its column
      const targetTask = tasks.find((t) => t.id === overId);
      if (targetTask) {
        newStatus = targetTask.status;
      }
    }

    if (!newStatus) return;

    // Find the task being moved
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === newStatus) return;

    // Optimistic update
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus as TaskStatus } : t))
    );

    try {
      await apiClient.update_task({
        task_id: taskId,
        status: newStatus,
      });
      toast.success('Task moved');
    } catch (error) {
      // Revert on error
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: task.status } : t))
      );
      console.error('Failed to update task:', error);
      toast.error('Failed to move task');
    }
  };

  const handleCreateTask = async (status: TaskStatus) => {
    if (!newTaskTitle.trim()) return;

    try {
      const response = await apiClient.create_task({
        project_id: projectId,
        title: newTaskTitle.trim(),
        description: null,
        priority: 'medium',
        order_index: 0,
      });

      const data = await response.json();
      if (data.success) {
        await loadTasks();
        setNewTaskTitle('');
        setShowNewTaskForm(null);
        toast.success('Task created');
      }
    } catch (error) {
      console.error('Failed to create task:', error);
      toast.error('Failed to create task');
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return;

    const originalTasks = [...tasks];
    setTasks((prev) => prev.filter((t) => t.id !== taskId));

    try {
      await apiClient.delete_task({ taskId });
      toast.success('Task deleted');
    } catch (error) {
      setTasks(originalTasks);
      console.error('Failed to delete task:', error);
      toast.error('Failed to delete task');
    }
  };

  const handleUpdateTaskTitle = async (taskId: string, newTitle: string) => {
    if (!newTitle.trim()) return;

    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.title === newTitle.trim()) {
      setEditingTaskId(null);
      return;
    }

    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, title: newTitle.trim() } : t))
    );
    setEditingTaskId(null);

    try {
      await apiClient.update_task({
        task_id: taskId,
        title: newTitle.trim(),
      });
      toast.success('Task updated');
    } catch (error) {
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, title: task.title } : t))
      );
      console.error('Failed to update task:', error);
      toast.error('Failed to update task');
    }
  };

  const activeTask = activeId ? tasks.find((t) => t.id === activeId) : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-muted-foreground">Loading tasks...</p>
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 h-full overflow-x-auto p-6">
        {columns.map((column) => (
          <DropZone
            key={column.id}
            column={column}
            isOver={overId === column.id}
            showNewTaskForm={showNewTaskForm === column.id}
            newTaskTitle={newTaskTitle}
            onNewTaskTitleChange={setNewTaskTitle}
            onCreateTask={() => handleCreateTask(column.id)}
            onShowNewTaskForm={() => setShowNewTaskForm(column.id)}
            onCancelNewTask={() => {
              setShowNewTaskForm(null);
              setNewTaskTitle('');
            }}
            editingTaskId={editingTaskId}
            editingTitle={editingTitle}
            onStartEdit={(taskId, title) => {
              setEditingTaskId(taskId);
              setEditingTitle(title);
            }}
            onSaveEdit={(taskId) => handleUpdateTaskTitle(taskId, editingTitle)}
            onCancelEdit={() => setEditingTaskId(null)}
            onTitleChange={setEditingTitle}
            onDeleteTask={handleDeleteTask}
          />
        ))}
      </div>

      <DragOverlay>
        {activeTask ? (
          <div className="bg-card border border-border rounded-md p-3 shadow-lg opacity-90 w-80">
            <div className="flex items-start gap-2">
              <GripVertical className="h-4 w-4 text-muted-foreground mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">
                  {activeTask.title}
                </p>
                {activeTask.description && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {activeTask.description}
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};

// DropZone Component
interface DropZoneProps {
  column: Column;
  isOver: boolean;
  showNewTaskForm: boolean;
  newTaskTitle: string;
  onNewTaskTitleChange: (title: string) => void;
  onCreateTask: () => void;
  onShowNewTaskForm: () => void;
  onCancelNewTask: () => void;
  editingTaskId: string | null;
  editingTitle: string;
  onStartEdit: (taskId: string, title: string) => void;
  onSaveEdit: (taskId: string) => void;
  onCancelEdit: () => void;
  onTitleChange: (title: string) => void;
  onDeleteTask: (taskId: string) => void;
}

const DropZone = ({
  column,
  isOver,
  showNewTaskForm,
  newTaskTitle,
  onNewTaskTitleChange,
  onCreateTask,
  onShowNewTaskForm,
  onCancelNewTask,
  editingTaskId,
  editingTitle,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onTitleChange,
  onDeleteTask,
}: DropZoneProps) => {
  const { setNodeRef } = useDroppable({
    id: column.id,
  });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'flex-shrink-0 w-80 flex flex-col bg-muted/30 rounded-lg border-2 transition-colors',
        isOver ? 'border-primary bg-muted/50' : 'border-transparent'
      )}
    >
      {/* Column Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm text-foreground">
            {column.title}
            <span className="ml-2 text-xs text-muted-foreground">
              ({column.tasks.length})
            </span>
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowNewTaskForm}
            className="h-6 w-6 p-0"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tasks List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[200px]">
        {showNewTaskForm && (
          <div className="bg-card border border-border rounded-md p-3 shadow-sm">
            <input
              type="text"
              value={newTaskTitle}
              onChange={(e) => onNewTaskTitleChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onCreateTask();
                if (e.key === 'Escape') onCancelNewTask();
              }}
              placeholder="Enter task title..."
              className="w-full px-2 py-1 text-sm bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
            <div className="flex gap-2 mt-2">
              <Button
                size="sm"
                onClick={onCreateTask}
                className="h-7 text-xs"
              >
                Add
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={onCancelNewTask}
                className="h-7 text-xs"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {column.tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            isEditing={editingTaskId === task.id}
            editingTitle={editingTitle}
            onStartEdit={() => onStartEdit(task.id, task.title)}
            onSaveEdit={() => onSaveEdit(task.id)}
            onCancelEdit={onCancelEdit}
            onTitleChange={onTitleChange}
            onDelete={() => onDeleteTask(task.id)}
          />
        ))}

        {column.tasks.length === 0 && !showNewTaskForm && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No tasks yet
          </div>
        )}
      </div>
    </div>
  );
};

// TaskCard Component
interface TaskCardProps {
  task: Task;
  isEditing: boolean;
  editingTitle: string;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onTitleChange: (title: string) => void;
  onDelete: () => void;
}

const TaskCard = ({
  task,
  isEditing,
  editingTitle,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onTitleChange,
  onDelete,
}: TaskCardProps) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={cn(
        'bg-card border border-border rounded-md p-3 shadow-sm hover:shadow-md transition-all group',
        isDragging && 'opacity-50'
      )}
    >
      <div className="flex items-start gap-2">
        <GripVertical className="h-4 w-4 text-muted-foreground mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <input
              type="text"
              value={editingTitle}
              onChange={(e) => onTitleChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onSaveEdit();
                if (e.key === 'Escape') onCancelEdit();
              }}
              onBlur={onSaveEdit}
              className="w-full px-2 py-1 text-sm bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <p
              className="text-sm font-medium text-foreground cursor-text"
              onClick={(e) => {
                e.stopPropagation();
                onStartEdit();
              }}
            >
              {task.title}
            </p>
          )}
          {task.description && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
              {task.description}
            </p>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-destructive/10 rounded"
          title="Delete task"
        >
          <Trash2 className="h-3 w-3 text-destructive" />
        </button>
      </div>
    </div>
  );
};
