import concurrent.futures
import threading
import time
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
        max_queue_size: Optional[int] = Config.POOL_MAX_SIZE,
        task_timeout_threshold: float = Config.POOL_TIMEOUT_THRESHOLD,      # секунд — порог "зависания"
        health_check_interval: float = 10.0       # секунд — интервал проверки
    ):
        self._pool_generation = 0
        self._on_task_start = None
        self._on_task_complete = None
        self._on_task_error = None
        self._on_pool_reset = None

        resolved_workers = max_workers if max_workers is not None else Config.POOL_SIZE
        if resolved_workers is None:
            resolved_workers = 10
        resolved_workers = max(1, int(resolved_workers))

        resolved_queue_size = max_queue_size if max_queue_size is not None else Config.POOL_MAX_SIZE
        if resolved_queue_size is None:
            resolved_queue_size = 5 * resolved_workers
        resolved_queue_size = max(1, int(resolved_queue_size))

        self._max_workers = resolved_workers
        self._thread_name_prefix = thread_name_prefix
        self._max_queue_size = resolved_queue_size
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
        self._peak_active_at: Optional[datetime] = None
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
                        self._peak_active_at = start_time

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
                    'peak_active_at': self._peak_active_at.timestamp() * 1000 if self._peak_active_at else None,
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


@dataclass
class OwnerPoolState:
    """Runtime profile for task owner/plugin."""
    inflight: int = 0
    success_count: int = 0
    fail_count: int = 0
    timeout_like_count: int = 0
    forced_quarantine_until: float = 0.0
    preferred_pool: str = "safe"
    avg_duration_ms: float = 0.0
    duration_samples: int = 0


class AdaptiveThreadPoolRouter:
    """
    Routes tasks between trusted, medium and quarantine pools.

    Default behavior is safe-by-default: unknown owners go to quarantine pool.
    """

    def __init__(
        self,
        pool_name: str,
        trusted_queue_size: Optional[int] = None,
        medium_queue_size: Optional[int] = None,
        safe_queue_size: Optional[int] = None,
        task_timeout_threshold: float = Config.POOL_TIMEOUT_THRESHOLD,
        health_check_interval: float = 10.0,
        promotion_success_threshold_medium: int = 8,
        promotion_success_threshold: int = 20,
        max_failure_ratio_for_promotion: float = 0.05,
        fast_task_threshold_ms: Optional[float] = None,
        medium_task_threshold_ms: Optional[float] = None,
        threshold_window_size: int = 500,
        threshold_min_samples: int = 50,
        timeout_like_degrade_threshold: int = 3,
        quarantine_duration_seconds: int = 300,
    ):
        pool_size_cfg = Config.POOL_SIZE if Config.POOL_SIZE is not None else 10
        pool_max_size_cfg = Config.POOL_MAX_SIZE if Config.POOL_MAX_SIZE is not None else (int(pool_size_cfg) * 5)
        base_workers = max(1, int(pool_size_cfg))
        base_queue = max(5, int(pool_max_size_cfg))

        trusted_workers = base_workers
        medium_workers = base_workers
        safe_workers = base_workers
        trusted_queue_size = trusted_queue_size if trusted_queue_size is not None else base_queue
        medium_queue_size = medium_queue_size if medium_queue_size is not None else max(10, base_queue // 2)
        safe_queue_size = safe_queue_size if safe_queue_size is not None else max(5, base_queue // 4)

        self._name = pool_name
        self._safe_pool = MonitoredThreadPool(
            max_workers=safe_workers,
            thread_name_prefix=f"{pool_name}.safe",
            max_queue_size=safe_queue_size,
            task_timeout_threshold=task_timeout_threshold,
            health_check_interval=health_check_interval,
        )
        self._medium_pool = MonitoredThreadPool(
            max_workers=medium_workers,
            thread_name_prefix=f"{pool_name}.medium",
            max_queue_size=medium_queue_size,
            task_timeout_threshold=task_timeout_threshold,
            health_check_interval=health_check_interval,
        )
        self._trusted_pool = MonitoredThreadPool(
            max_workers=trusted_workers,
            thread_name_prefix=f"{pool_name}.trusted",
            max_queue_size=trusted_queue_size,
            task_timeout_threshold=task_timeout_threshold,
            health_check_interval=health_check_interval,
        )
        self._task_timeout_threshold = task_timeout_threshold
        self._promotion_success_threshold_medium = max(1, promotion_success_threshold_medium)
        self._promotion_success_threshold = max(1, promotion_success_threshold)
        self._max_failure_ratio_for_promotion = max(0.0, max_failure_ratio_for_promotion)
        self._task_timeout_threshold_ms = self._task_timeout_threshold * 1000.0
        self._auto_thresholds_enabled = fast_task_threshold_ms is None or medium_task_threshold_ms is None
        self._fast_task_threshold_ms = (
            max(0.1, float(fast_task_threshold_ms))
            if fast_task_threshold_ms is not None
            else 50.0
        )
        self._medium_task_threshold_ms = (
            max(self._fast_task_threshold_ms, float(medium_task_threshold_ms))
            if medium_task_threshold_ms is not None
            else 500.0
        )
        self._threshold_window_size = max(100, threshold_window_size)
        self._threshold_min_samples = max(20, threshold_min_samples)
        self._recent_durations_ms = deque(maxlen=self._threshold_window_size)
        self._last_p40_ms = 0.0
        self._last_p80_ms = 0.0
        self._last_p95_ms = 0.0
        self._timeout_like_degrade_threshold = max(1, timeout_like_degrade_threshold)
        self._quarantine_duration_seconds = max(1, quarantine_duration_seconds)

        self._owner_states: Dict[str, OwnerPoolState] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return sorted_values[0]
        rank = (len(sorted_values) - 1) * max(0.0, min(1.0, percentile))
        low = int(rank)
        high = min(low + 1, len(sorted_values) - 1)
        frac = rank - low
        return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac

    def _update_auto_thresholds(self):
        if not self._auto_thresholds_enabled:
            return
        if len(self._recent_durations_ms) < self._threshold_min_samples:
            return
        durations = sorted(self._recent_durations_ms)
        p40 = self._percentile(durations, 0.40)
        p80 = self._percentile(durations, 0.80)
        p95 = self._percentile(durations, 0.95)
        self._last_p40_ms = p40
        self._last_p80_ms = p80
        self._last_p95_ms = p95

        fast = max(1.0, min(250.0, p40))
        medium_floor = 20.0
        medium_cap = max(medium_floor, self._task_timeout_threshold_ms * 0.5)
        medium = max(medium_floor, min(medium_cap, p80))

        self._fast_task_threshold_ms = fast
        self._medium_task_threshold_ms = medium

    def _get_owner_state(self, owner: str) -> OwnerPoolState:
        with self._lock:
            state = self._owner_states.get(owner)
            if state is None:
                state = OwnerPoolState()
                self._owner_states[owner] = state
            return state

    def _select_pool_name(self, owner: str, state: OwnerPoolState) -> str:
        now_ts = time.monotonic()
        if state.forced_quarantine_until > now_ts:
            return "safe"
        return state.preferred_pool or "safe"

    def _select_pool(self, pool_name: str) -> MonitoredThreadPool:
        if pool_name == "trusted":
            return self._trusted_pool
        if pool_name == "medium":
            return self._medium_pool
        return self._safe_pool

    def _mark_owner_result(self, owner: str, success: bool, duration: float):
        now_ts = time.monotonic()
        with self._lock:
            state = self._owner_states.get(owner)
            if state is None:
                return

            if success:
                state.success_count += 1
            else:
                state.fail_count += 1

            duration_ms = duration * 1000.0
            self._recent_durations_ms.append(duration_ms)
            self._update_auto_thresholds()

            state.duration_samples += 1
            if state.duration_samples == 1:
                state.avg_duration_ms = duration_ms
            else:
                # Exponential moving average to react to behavior changes.
                alpha = 0.2
                state.avg_duration_ms = (state.avg_duration_ms * (1.0 - alpha)) + (duration_ms * alpha)

            if duration > self._task_timeout_threshold:
                state.timeout_like_count += 1
            elif success and state.timeout_like_count > 0:
                state.timeout_like_count -= 1

            total = state.success_count + state.fail_count
            failure_ratio = (state.fail_count / total) if total else 0.0

            if state.timeout_like_count >= self._timeout_like_degrade_threshold:
                state.preferred_pool = "safe"
                state.forced_quarantine_until = now_ts + self._quarantine_duration_seconds
                _logger.warning(
                    f"Owner '{owner}' moved to quarantine for {self._quarantine_duration_seconds}s "
                    f"(timeout-like tasks: {state.timeout_like_count})"
                )
                state.timeout_like_count = 0
                return

            can_promote_to_medium = (
                total >= min(self._promotion_success_threshold_medium, 1)
                and state.success_count >= min(self._promotion_success_threshold_medium, 1)
                and failure_ratio <= self._max_failure_ratio_for_promotion
            )
            can_promote_to_trusted = (
                total >= self._promotion_success_threshold
                and state.success_count >= self._promotion_success_threshold
                and failure_ratio <= self._max_failure_ratio_for_promotion
            )
            if state.avg_duration_ms > self._medium_task_threshold_ms:
                state.preferred_pool = "safe"
            elif can_promote_to_trusted and state.avg_duration_ms <= self._fast_task_threshold_ms and state.preferred_pool != "trusted":
                state.preferred_pool = "trusted"
                _logger.debug(
                    f"Owner '{owner}' promoted to trusted pool "
                    f"(total={total}, fail_ratio={failure_ratio:.3f}, avg={state.avg_duration_ms:.2f}ms)"
                )
            elif can_promote_to_medium and state.avg_duration_ms <= self._medium_task_threshold_ms and state.preferred_pool == "safe":
                state.preferred_pool = "medium"
                _logger.debug(
                    f"Owner '{owner}' promoted to medium pool "
                    f"(total={total}, fail_ratio={failure_ratio:.3f}, avg={state.avg_duration_ms:.2f}ms)"
                )
            elif state.avg_duration_ms > self._fast_task_threshold_ms and state.preferred_pool == "trusted":
                state.preferred_pool = "medium"
            elif failure_ratio > max(self._max_failure_ratio_for_promotion * 2, 0.10):
                if state.preferred_pool == "trusted":
                    state.preferred_pool = "medium"
                else:
                    state.preferred_pool = "safe"

    def submit(
        self,
        fn: Callable,
        task_id: Optional[str] = None,
        owner: Optional[str] = None,
        *args,
        ignore_owner_limit: bool = False,
        **kwargs
    ) -> concurrent.futures.Future:
        owner_key = owner or "unknown"
        state = self._get_owner_state(owner_key)
        pool_name = self._select_pool_name(owner_key, state)

        with self._lock:
            state.inflight += 1

        def owner_wrapper():
            start = time.monotonic()
            ok = False
            try:
                result = fn(*args, **kwargs)
                ok = True
                return result
            finally:
                duration = time.monotonic() - start
                with self._lock:
                    owner_state = self._owner_states.get(owner_key)
                    if owner_state:
                        owner_state.inflight = max(0, owner_state.inflight - 1)
                self._mark_owner_result(owner_key, ok, duration)

        try:
            if pool_name == "trusted":
                pool_chain = ("trusted", "medium", "safe")
            elif pool_name == "medium":
                pool_chain = ("medium", "safe")
            else:
                pool_chain = ("safe",)

            last_error = None
            for candidate in pool_chain:
                try:
                    pool = self._select_pool(candidate)
                    return pool.submit(owner_wrapper, task_id=task_id)
                except RuntimeError as err:
                    err_text = str(err)
                    if "overloaded" in err_text or "queue size" in err_text:
                        last_error = err
                        _logger.warning(
                            f"Pool '{self._name}.{candidate}' overloaded for owner '{owner_key}', "
                            f"trying lower tier"
                        )
                        continue
                    raise

            if last_error:
                raise last_error
            raise RuntimeError(f"Unable to submit task '{task_id}' for owner '{owner_key}'")
        except Exception:
            with self._lock:
                state.inflight = max(0, state.inflight - 1)
                state.fail_count += 1
                state.preferred_pool = "safe"
            raise

    def get_stats(self):
        with self._lock:
            owners = {
                name: {
                    "inflight": s.inflight,
                    "success_count": s.success_count,
                    "fail_count": s.fail_count,
                    "timeout_like_count": s.timeout_like_count,
                    "avg_duration_ms": round(s.avg_duration_ms, 3),
                    "duration_samples": s.duration_samples,
                    "preferred_pool": s.preferred_pool,
                    "forced_quarantine_until": s.forced_quarantine_until,
                }
                for name, s in self._owner_states.items()
            }
        return {
            "router_name": self._name,
            "routing_thresholds": {
                "auto_enabled": self._auto_thresholds_enabled,
                "fast_task_threshold_ms": round(self._fast_task_threshold_ms, 3),
                "medium_task_threshold_ms": round(self._medium_task_threshold_ms, 3),
                "sample_count": len(self._recent_durations_ms),
                "min_samples_for_auto": self._threshold_min_samples,
                "window_size": self._threshold_window_size,
                "p40_ms": round(self._last_p40_ms, 3),
                "p80_ms": round(self._last_p80_ms, 3),
                "p95_ms": round(self._last_p95_ms, 3),
            },
            "safe_pool": self._safe_pool.get_monitoring_stats(),
            "medium_pool": self._medium_pool.get_monitoring_stats(),
            "trusted_pool": self._trusted_pool.get_monitoring_stats(),
            "owners": owners,
        }

    def shutdown(self, wait: bool = True):
        self._safe_pool.shutdown(wait=wait)
        self._medium_pool.shutdown(wait=wait)
        self._trusted_pool.shutdown(wait=wait)
