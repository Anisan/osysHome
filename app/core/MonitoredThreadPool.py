import concurrent.futures
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from collections import deque
from settings import Config
from app.logging_config import getLogger

_logger = getLogger('thread_pools')

@dataclass
class PoolStats:
    """Статистика использования пула потоков"""
    active_threads: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_submitted: int
    average_execution_time: float
    peak_active_threads: int
    pool_utilization: float

class MonitoredThreadPool:
    """Пул потоков с мониторингом использования"""

    def __init__(self, max_workers: int = Config.POOL_SIZE, thread_name_prefix: str = "Worker"):
        self._on_task_start = None
        self._on_task_complete = None
        self._on_task_error = None
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self._max_workers = max_workers
        self._lock = threading.Lock()

        # Статистика
        self._active_tasks: Dict[str, datetime] = {}
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._total_submitted = 0
        self._execution_times = []
        self._peak_active = 0

        # Мониторинг пула потоков
        self._max_concurrent_tasks = 0

        # Мониторинг времени выполнения
        self._execution_times = deque(maxlen=100)
        self._total_execution_time = 0
        self._avg_execution_time = 0
        self._min_execution_time = float('inf')
        self._max_execution_time = 0

        # История для графиков (последние 100 записей)
        self._execution_history = deque(maxlen=100)

        _logger.info(f"Init pool threads '{thread_name_prefix}' (max workers: {max_workers})")

    def submit(self, fn: Callable, task_id=None, *args, **kwargs) -> concurrent.futures.Future:
        """Отправляет задачу в пул с мониторингом"""
        with self._lock:
            self._total_submitted += 1
            if not task_id:
                task_id = f"task_{self._total_submitted}"

        def monitored_wrapper():
            start_time = datetime.now()

            with self._lock:
                self._active_tasks[task_id] = start_time
                if len(self._active_tasks) > self._peak_active:
                    self._peak_active = len(self._active_tasks)

            if self._on_task_start:
                self._on_task_start(task_id, start_time)
            else:
                _logger.debug(f"Starting task '{task_id}'")

            success = False
            error = None
            try:
                result = fn(*args, **kwargs)
                success = True
            except Exception as e:
                result = None
                error = e
                raise
            finally:
                with self._lock:
                    if success:
                        self._completed_tasks += 1
                    else:
                        self._failed_tasks += 1

                    if task_id in self._active_tasks:
                        del self._active_tasks[task_id]

                    execution_time = (datetime.now() - start_time).total_seconds()
                    self._execution_times.append(execution_time)

                    # Обновляем статистику времени выполнения
                    if len(self._execution_times) == 100:
                        self._total_execution_time -= self._execution_times[0]

                    self._execution_times.append(execution_time)
                    self._total_execution_time += execution_time

                    if self._execution_times:
                        self._min_execution_time = min(self._execution_times)
                        self._max_execution_time = max(self._execution_times)
                        self._avg_execution_time = self._total_execution_time / len(self._execution_times)

                    # Добавляем в историю для графиков
                    current_time = datetime.now()
                    self._execution_history.append({
                        'timestamp': current_time.timestamp() * 1000,  # Миллисекунды для Chart.js
                        'time': current_time.strftime('%H:%M:%S.%f')[:-3],
                        'duration': execution_time,
                        'task_name': task_id,
                        'success': success
                    })

                    # Ограничиваем историю времени выполнения
                    if len(self._execution_times) > 1000:
                        self._execution_times = self._execution_times[-500:]

                    if success:
                        if self._on_task_complete:
                            self._on_task_complete(task_id, execution_time)
                        else:
                            _logger.debug(f"Completed task '{task_id}' in {execution_time:.2f}s")
                    else:
                        if self._on_task_error:
                            self._on_task_error(task_id, str(error))
                        else:
                            _logger.exception(f"Task '{task_id}' failed: {error}")

            return result

        return self._executor.submit(monitored_wrapper)

    def get_stats(self) -> PoolStats:
        """Возвращает текущую статистику пула"""
        with self._lock:
            avg_time = (
                sum(self._execution_times) / len(self._execution_times)
                if self._execution_times else 0.0
            )

            utilization = len(self._active_tasks) / self._max_workers * 100

            return PoolStats(
                active_threads=len(self._active_tasks),
                pending_tasks=self._executor._work_queue.qsize() if hasattr(self._executor, '_work_queue') else 0,
                completed_tasks=self._completed_tasks,
                failed_tasks=self._failed_tasks,
                total_submitted=self._total_submitted,
                average_execution_time=avg_time,
                peak_active_threads=self._peak_active,
                pool_utilization=utilization
            )

    def get_monitoring_stats(self):
        """Получение полной статистики мониторинга"""
        with self._lock:
            utilization = len(self._active_tasks) / self._max_workers * 100
            return {
                'thread_pool': {
                    'max_workers': self._max_workers,
                    'active_tasks': self._active_tasks,
                    'completed_tasks': self._completed_tasks,
                    'failed_tasks': self._failed_tasks,
                    'max_concurrent_tasks': self._peak_active,
                    'queue_size': len(self._executor._work_queue.queue) if hasattr(self._executor._work_queue, 'queue') else 0,
                    'pool_utilization': utilization
                },
                'execution_time': {
                    'avg_execution_time': round(self._avg_execution_time, 3) if self._avg_execution_time else 0,
                    'min_execution_time': round(self._min_execution_time, 3) if self._min_execution_time != float('inf') else 0,
                    'max_execution_time': round(self._max_execution_time, 3),
                    'total_execution_time': round(self._total_execution_time, 3)
                },
                'history': list(self._execution_history)
            }

    def set_monitoring_callbacks(self,
                               on_start: Optional[Callable] = None,  # noqa
                               on_complete: Optional[Callable] = None,  # noqa
                               on_error: Optional[Callable] = None):  # noqa
        """Устанавливает колбэки для мониторинга событий"""
        self._on_task_start = on_start
        self._on_task_complete = on_complete
        self._on_task_error = on_error

    def shutdown(self, wait: bool = True):
        """Корректное завершение работы пула"""
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
