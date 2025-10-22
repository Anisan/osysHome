import concurrent.futures
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from collections import deque
from app.configuration import Config
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
    rejected_tasks: int

class MonitoredThreadPool:
    """Пул потоков с мониторингом использования и защитой от зависаний"""

    def __init__(
        self,
        max_workers: int = Config.POOL_SIZE,
        thread_name_prefix: str = "Worker",
        max_queue_size: Optional[int] = None,
        task_timeout_threshold: float = Config.POOL_TIMEOUT_THRESHOLD,      # секунд — порог "зависания"
        health_check_interval: float = 10.0       # секунд — интервал проверки
    ):
        self._pool_generation = 0
        self._on_task_start = None
        self._on_task_complete = None
        self._on_task_error = None
        self._on_pool_reset = None

        self._max_workers = max_workers
        self._thread_name_prefix = thread_name_prefix
        self._max_queue_size = max_queue_size or (2 * max_workers)
        self._task_timeout_threshold = task_timeout_threshold
        self._health_check_interval = health_check_interval

        self._lock = threading.Lock()
        self._rejected_tasks = 0

        # Статистика
        self._active_tasks: Dict[str, datetime] = {}
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._total_submitted = 0
        self._execution_times = deque(maxlen=100)
        self._total_execution_time = 0
        self._avg_execution_time = 0
        self._min_execution_time = float('inf')
        self._max_execution_time = 0
        self._peak_active = 0
        self._execution_history = deque(maxlen=100)

        # Health checker control
        self._stop_health_checker = threading.Event()
        self._health_checker_thread = None

        # Создаём пул
        self._create_executor()
        self._start_health_checker()

        _logger.info(
            f"Init pool threads '{thread_name_prefix}' "
            f"(max workers: {max_workers}, max queue: {self._max_queue_size}, "
            f"task timeout threshold: {task_timeout_threshold}s)"
        )

    def _create_executor(self):
        """Создаёт новый ThreadPoolExecutor и сбрасывает мониторинг старых задач"""
        self._pool_generation += 1
        # Сохраняем статистику по "потерянным" задачам
        lost_tasks = len(self._active_tasks)
        if lost_tasks > 0:
            if self._on_pool_reset:
                self._on_pool_reset()
            _logger.warning(
                f"Pool reset: {lost_tasks} active tasks will be orphaned "
                f"(considered failed)."
            )
            lost_task_ids = list(self._active_tasks.keys())
            _logger.warning(f"Orphaned tasks: {lost_task_ids}")
            # Считаем их проваленными
            self._failed_tasks += lost_tasks
            # Очищаем активные задачи — они больше не отслеживаются
            self._active_tasks.clear()
            # Сбрасываем пиковое значение? или оставляем?
            # self._peak_active = 0  # опционально

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix=self._thread_name_prefix
        )

    def _start_health_checker(self):
        """Запускает фоновый поток для проверки здоровья пула"""
        def health_check_loop():
            while not self._stop_health_checker.is_set():
                try:
                    if not self.is_healthy():
                        _logger.critical(f"Pool {self._thread_name_prefix} is completely stuck — replacing executor")
                        with self._lock:
                            old_executor = self._executor
                            old_executor.shutdown(wait=False)  # не ждём зависшие задачи
                            self._create_executor()
                except Exception as e:
                    _logger.error(f"Error in health checker: {e}")
                finally:
                    self._stop_health_checker.wait(timeout=self._health_check_interval)

        self._health_checker_thread = threading.Thread(
            target=health_check_loop,
            daemon=True,
            name=f"HealthPoolChecker-{self._thread_name_prefix}"
        )
        self._health_checker_thread.start()

    def is_healthy(self) -> bool:
        """
        Возвращает False только если:
        - Есть активные задачи,
        - Их количество >= max_workers (все потоки заняты),
        - И ВСЕ они выполняются дольше task_timeout_threshold.
        """
        now = datetime.now()
        with self._lock:
            active_count = len(self._active_tasks)
            if active_count == 0:
                return True
            if active_count < self._max_workers:
                return True

            # Проверяем, все ли задачи "зависли"
            all_stuck = True
            oldest_duration = 0.0
            for start_time in self._active_tasks.values():
                duration = (now - start_time).total_seconds()
                oldest_duration = max(oldest_duration, duration)
                if duration <= self._task_timeout_threshold:
                    all_stuck = False
                    break

            if all_stuck:
                _logger.warning(
                    f"Pool UNHEALTHY: all {active_count}/{self._max_workers} workers "
                    f"are stuck on tasks exceeding {self._task_timeout_threshold}s. "
                    f"Oldest task: {oldest_duration:.1f}s"
                )
                return False

            return True

    def submit(
        self,
        fn: Callable,
        task_id: Optional[str] = None,
        *args,
        **kwargs
    ) -> concurrent.futures.Future:
        """Отправляет задачу в пул с мониторингом и защитой от перегрузки"""
        # Проверка переполнения очереди
        pending = self._executor._work_queue.qsize()
        if pending >= self._max_queue_size:
            with self._lock:
                self._rejected_tasks += 1
            task_id = task_id or "unknown"
            _logger.warning(
                f"Task '{task_id}' rejected: queue full "
                f"({pending} >= {self._max_queue_size}). "
                f"Total rejected: {self._rejected_tasks}"
            )
            raise RuntimeError(
                f"ThreadPool '{self._thread_name_prefix}' overloaded: "
                f"queue size {pending} >= {self._max_queue_size}"
            )

        with self._lock:
            self._total_submitted += 1
            if not task_id:
                task_id = f"task_{self._total_submitted}"
            # Генерируем уникальный внутренний ключ для отслеживания
            internal_task_key = f"{task_id}_{self._total_submitted}"
            task_generation = self._pool_generation  # Проверка на перезапуск пула

        def monitored_wrapper():
            current_thread = threading.current_thread()
            original_name = current_thread.name
            current_thread.name = f"{original_name} ({task_id})"
            start_time = datetime.now()
            success = False
            error = None
            try:
                with self._lock:
                    # Проверяем: не изменилось ли поколение?
                    if self._pool_generation != task_generation:
                        # Задача запущена в старом пуле, который уже заменён
                        _logger.warning(f"Task '{task_id}' skipped: pool generation changed")
                        return None
                    self._active_tasks[internal_task_key] = start_time
                    if len(self._active_tasks) > self._peak_active:
                        self._peak_active = len(self._active_tasks)

                if self._on_task_start:
                    self._on_task_start(task_id, start_time)
                else:
                    _logger.debug(f"Starting task '{task_id}'")

                result = fn(*args, **kwargs)
                success = True
            except Exception as e:
                result = None
                error = e
                raise
            finally:
                # Восстанавливаем имя потока
                current_thread.name = original_name

                with self._lock:
                    # Если поколение изменилось — игнорируем
                    if self._pool_generation != task_generation:
                        _logger.warning(f"Task '{task_id}' result ignored: pool was reset")
                        return
                    self._active_tasks.pop(internal_task_key, None)
                    if success:
                        self._completed_tasks += 1
                    else:
                        self._failed_tasks += 1

                    execution_time = (datetime.now() - start_time).total_seconds()

                    # Обновляем статистику времени выполнения
                    if len(self._execution_times) == 100:
                        self._total_execution_time -= self._execution_times[0]

                    self._execution_times.append(execution_time)
                    self._total_execution_time = sum(self._execution_times)

                    if self._execution_times:
                        self._min_execution_time = min(self._execution_times)
                        self._max_execution_time = max(self._execution_times)
                        self._avg_execution_time = self._total_execution_time / len(self._execution_times)

                    # Добавляем в историю для графиков
                    current_time = datetime.now()
                    self._execution_history.append({
                        'timestamp': current_time.timestamp() * 1000,
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
            utilization = len(self._active_tasks) / self._max_workers * 100 if self._max_workers else 0

            return PoolStats(
                active_threads=len(self._active_tasks),
                pending_tasks=self._executor._work_queue.qsize(),
                completed_tasks=self._completed_tasks,
                failed_tasks=self._failed_tasks,
                total_submitted=self._total_submitted,
                average_execution_time=avg_time,
                peak_active_threads=self._peak_active,
                pool_utilization=utilization,
                rejected_tasks=self._rejected_tasks
            )

    def get_monitoring_stats(self):
        """Получение полной статистики мониторинга"""
        with self._lock:
            utilization = len(self._active_tasks) / self._max_workers * 100 if self._max_workers else 0
            return {
                'thread_pool': {
                    'pool_generation': self._pool_generation,
                    'max_workers': self._max_workers,
                    'active_tasks': dict(self._active_tasks),
                    'completed_tasks': self._completed_tasks,
                    'failed_tasks': self._failed_tasks,
                    'rejected_tasks': self._rejected_tasks,
                    'max_concurrent_tasks': self._peak_active,
                    'queue_size': self._executor._work_queue.qsize(),
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

    def set_monitoring_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_pool_reset: Optional[Callable] = None,
    ):
        """Устанавливает колбэки для мониторинга событий"""
        self._on_task_start = on_start
        self._on_task_complete = on_complete
        self._on_task_error = on_error
        self._on_pool_reset = on_pool_reset

    def shutdown(self, wait: bool = True):
        """Корректное завершение работы пула"""
        self._stop_health_checker.set()
        if self._health_checker_thread and self._health_checker_thread.is_alive():
            self._health_checker_thread.join(timeout=2.0)
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
