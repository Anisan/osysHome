import datetime
import time
from enum import Enum
from dateutil import parser
from dateutil.parser._parser import ParserError
import json
from sqlalchemy import delete
from flask_login import current_user
from app.database import session_scope,row2dict, convert_utc_to_local, convert_local_to_utc, get_now_to_utc
from app.core.lib.common import (
    getModule,
    getModulesByAction,
    addNotify,
    writeCoreSystemStatsMetric,
    incrementCoreSystemStatsMetric,
    flushBufferedCoreSystemStatsMetrics,
    scheduleSystemStatsWsNotify,
    invalidateSystemStatsEnabledCache,
)
from app.core.lib.constants import CategoryNotify, SYSTEM_STATS_OBJECT, PropertyType
from app.core.main.reactive_chain import chain_enter, chain_exit, chain_format
from app.core.models.Clasess import Object, Property, Value, History
from app.core.lib.common import setTimeout
from app.core.lib.execute import execute_and_capture_output
from app.logging_config import getLogger
from app.core.MonitoredThreadPool import AdaptiveThreadPoolRouter
from app.configuration import Config
from app.core.lib.constants import SYSTEM_STATS_SOURCE
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional
import logging
from app.core.lib.converters.color_value import (
    parse as parse_color_value,
    to_universal as to_universal_color,
    from_universal as from_universal_color,
    encode as encode_color_value,
    decode as decode_color_value,
    detect_format as detect_color_format,
    merge_xy_luminance,
)

_logger = getLogger('object')


class ObjectLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds object name to log messages"""
    def process(self, msg, kwargs):
        object_name = self.extra.get('object_name', 'Unknown')
        return f'[{object_name}] {msg}', kwargs

# Глобальный роутер потоков для linkedProperty/proxy задач.
# Safe-by-default: неизвестные/проблемные плагины попадают в quarantine pool.
_poolLinkedProperty = AdaptiveThreadPoolRouter(
    pool_name="linkedProperty",
    trusted_queue_size=Config.POOL_MAX_SIZE if Config.POOL_MAX_SIZE is not None else ((Config.POOL_SIZE if Config.POOL_SIZE is not None else 10) * 5),
    medium_queue_size=max(10, (Config.POOL_MAX_SIZE if Config.POOL_MAX_SIZE is not None else (Config.POOL_SIZE if Config.POOL_SIZE is not None else 10) * 5)),
    safe_queue_size=max(5, (Config.POOL_MAX_SIZE if Config.POOL_MAX_SIZE is not None else (Config.POOL_SIZE if Config.POOL_SIZE is not None else 10) * 5)),
    promotion_success_threshold_medium=1,
    promotion_success_threshold=20,
    max_failure_ratio_for_promotion=0.05,
    timeout_like_degrade_threshold=3,
    quarantine_duration_seconds=300,
)


@dataclass
class ValueUpdate:
    """Структура для хранения обновления значения"""
    value_id: int
    value: str
    changed: datetime.datetime
    source: str
    save_history: bool
    history_value: Optional[str] = None
    history_only: bool = False  # Если True, обновляется только история, не само значение
    explicit_date: bool = False  # Если True, дата была указана явно (нужно проверять дубликаты)
    internal: bool = False  # Если True, запись от SystemStats — не учитывается во внешней статистике


class BatchWriter:
    """Батчер для групповой записи значений и истории в БД"""

    def __init__(self, flush_interval: float = 0.5):
        """
        Args:
            flush_interval: Интервал в секундах для принудительной записи батча
        """
        self.flush_interval = flush_interval
        self._lock = threading.Lock()
        self._batch: list[ValueUpdate] = []
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        # Статистика
        self._total_added = 0  # Всего добавлено записей
        self._total_flushed = 0  # Всего выполнено записей в БД
        self._total_values_updated = 0  # Всего обновлено значений
        self._total_history_inserted = 0  # Всего вставлено записей истории
        self._total_errors = 0  # Всего ошибок (внешние батчи)
        self._total_internal_errors = 0  # Ошибки батчей только с internal-записями
        self._total_internal_added = 0  # Внутренних записей (SystemStats)
        self._total_internal_values_updated = 0  # Внутренних обновлений значений
        self._total_internal_history_inserted = 0  # Внутренних вставок истории
        self._flush_history: deque = deque(maxlen=100)  # История последних flush
        self._last_flush_time: Optional[datetime.datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_time: Optional[datetime.datetime] = None
        self._start_worker()

    def _start_worker(self):
        """Запускает фоновый поток для периодической записи батчей"""
        def worker():
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=self.flush_interval)
                if not self._stop_event.is_set():
                    # Выполняем запись напрямую в этом потоке
                    self._flush_internal()

        self._worker_thread = threading.Thread(target=worker, daemon=True, name="BatchWriter")
        self._worker_thread.start()

    def add(self, value_update: ValueUpdate):
        """Добавляет запись в батч"""
        with self._lock:
            self._batch.append(value_update)
            self._total_added += 1
            if value_update.internal:
                self._total_internal_added += 1

    def flush(self):
        """Принудительно записывает текущий батч (асинхронно)"""
        # Запускаем запись в отдельном потоке, чтобы не блокировать вызывающий поток
        thread = threading.Thread(target=self._flush_internal, daemon=True, name="BatchWriterFlush")
        thread.start()

    def flush_sync(self):
        """Принудительно и синхронно записывает текущий батч (для init-сценариев)"""
        self._flush_internal()

    def _append_flush_history(
        self,
        *,
        duration_seconds: float,
        batch_size: int,
        values_count: int,
        history_count: int,
        success: bool,
        error: Optional[str] = None,
    ):
        self._flush_history.append({
            "duration_seconds": round(duration_seconds, 4),
            "batch_size": batch_size,
            "values_count": values_count,
            "history_count": history_count,
            "success": success,
            "error": error,
            "timestamp": convert_utc_to_local(get_now_to_utc()).isoformat(),
        })

    def _flush_internal(self):
        """Внутренний метод для записи батча (вызывается в отдельном потоке)"""
        start_time = time.time()
        values_count = 0
        history_count = 0

        try:
            with self._lock:
                if not self._batch:
                    execution_time = time.time() - start_time
                    self._append_flush_history(
                        duration_seconds=execution_time,
                        batch_size=0,
                        values_count=0,
                        history_count=0,
                        success=True,
                    )
                    return
                batch = self._batch[:]
                self._batch.clear()

            batch_size = len(batch)
            if not batch:
                execution_time = time.time() - start_time
                with self._lock:
                    self._append_flush_history(
                        duration_seconds=execution_time,
                        batch_size=0,
                        values_count=0,
                        history_count=0,
                        success=True,
                    )
                return

            with session_scope() as session:
                # Группируем обновления по value_id (последнее значение для каждого value_id)
                value_updates = {}
                history_records = []
                internal_by_value_id: dict[int, bool] = {}
                internal_history_count = 0

                for update_item in batch:
                    # Сохраняем последнее значение для каждого value_id только если не history_only
                    if not update_item.history_only:
                        value_updates[update_item.value_id] = {
                            'value': update_item.value,
                            'changed': update_item.changed,
                            'source': update_item.source
                        }
                        internal_by_value_id[update_item.value_id] = update_item.internal

                    # Собираем записи истории
                    if update_item.save_history and update_item.history_value is not None:
                        history_records.append({
                            'value_id': update_item.value_id,
                            'value': update_item.history_value,
                            'added': update_item.changed,
                            'source': update_item.source,
                            'explicit_date': update_item.explicit_date
                        })
                        if update_item.internal:
                            internal_history_count += 1

                # Bulk update для значений
                if value_updates:
                    values_count = len(value_updates)
                    # Используем bulk_update_mappings для эффективности
                    # Если не поддерживается, используем цикл с update
                    try:
                        update_mappings = [
                            {
                                'id': value_id,
                                'value': data['value'],
                                'changed': data['changed'],
                                'source': data['source']
                            }
                            for value_id, data in value_updates.items()
                        ]
                        session.bulk_update_mappings(Value, update_mappings)
                    except (AttributeError, TypeError):
                        # Fallback для старых версий SQLAlchemy
                        from sqlalchemy import update
                        for value_id, data in value_updates.items():
                            stmt = update(Value).where(Value.id == value_id).values(
                                value=data['value'],
                                changed=data['changed'],
                                source=data['source']
                            )
                            session.execute(stmt)

                # Bulk insert/update для истории
                if history_records:
                    history_count = 0
                    # Группируем по (value_id, added, source) для проверки дубликатов
                    history_by_key = {}
                    history_with_explicit_date = []
                    for record in history_records:
                        key = (record['value_id'], record['added'], record['source'])
                        history_by_key[key] = record
                        # Сохраняем информацию о том, была ли дата указана явно
                        # Проверяем дубликаты только для записей с явно указанной датой
                        if record.get('explicit_date', False):
                            history_with_explicit_date.append(key)
                    
                    # Проверяем существующие записи только для записей с явно указанной датой
                    # Если дата не указана явно (используется текущее время), вероятность дубликата крайне мала
                    existing_history = {}
                    if history_with_explicit_date:
                        # Собираем только записи с явно указанными датами для проверки
                        explicit_records = [history_by_key[key] for key in history_with_explicit_date]
                        value_ids = set(r['value_id'] for r in explicit_records)
                        added_dates = set(r['added'] for r in explicit_records)
                        sources = set(r['source'] for r in explicit_records)
                        existing_records = session.query(History).filter(
                            History.value_id.in_(value_ids),
                            History.added.in_(added_dates),
                            History.source.in_(sources)
                        ).all()
                        for record in existing_records:
                            key = (record.value_id, record.added, record.source)
                            existing_history[key] = record
                    
                    # Разделяем на обновления и вставки
                    history_inserts = []
                    
                    for key, record in history_by_key.items():
                        if key in existing_history:
                            # Обновляем существующую запись только если source совпадает
                            existing_record = existing_history[key]
                            existing_record.value = record['value']
                            # source уже совпадает, так как он в ключе
                            # Обновление применяется напрямую к объекту, будет сохранено при commit
                            history_count += 1
                        else:
                            # Вставляем новую запись (удаляем explicit_date из записи перед вставкой)
                            insert_record = {k: v for k, v in record.items() if k != 'explicit_date'}
                            history_inserts.append(insert_record)
                            history_count += 1
                    
                    # Выполняем bulk insert для новых записей
                    if history_inserts:
                        session.bulk_insert_mappings(History, history_inserts)
                    
                    # Обновления уже применены к объектам, они будут сохранены при commit

                session.commit()
                
                # Обновляем статистику при успехе
                execution_time = time.time() - start_time
                internal_values = sum(
                    1 for vid in value_updates if internal_by_value_id.get(vid, False)
                )
                with self._lock:
                    self._total_flushed += 1
                    self._total_values_updated += values_count
                    self._total_history_inserted += history_count
                    self._total_internal_values_updated += internal_values
                    self._total_internal_history_inserted += internal_history_count
                    self._last_flush_time = get_now_to_utc()
                    self._append_flush_history(
                        duration_seconds=execution_time,
                        batch_size=batch_size,
                        values_count=values_count,
                        history_count=history_count,
                        success=True,
                    )
                ext_values = values_count - internal_values
                ext_history = history_count - internal_history_count
                writeCoreSystemStatsMetric(
                    "batch_queue_size",
                    0,
                    description="Current batch queue size",
                    prop_type=PropertyType.Integer,
                    source=SYSTEM_STATS_SOURCE,
                )
                writeCoreSystemStatsMetric(
                    "batch_avg_flush_ms",
                    round(execution_time * 1000.0, 2),
                    description="Batch flush duration (ms, event-driven)",
                    prop_type=PropertyType.Float,
                    source=SYSTEM_STATS_SOURCE,
                )
                if ext_values > 0:
                    incrementCoreSystemStatsMetric(
                        "batch_values_updated",
                        ext_values,
                        description="External value updates",
                        source=SYSTEM_STATS_SOURCE,
                    )
                if ext_history > 0:
                    incrementCoreSystemStatsMetric(
                        "batch_history_inserted",
                        ext_history,
                        description="External history inserts",
                        source=SYSTEM_STATS_SOURCE,
                    )

        except Exception as ex:
            error_msg = str(ex)
            _logger.exception("Error in batch write: %s", ex, exc_info=True)
            execution_time = time.time() - start_time
            # Обновляем статистику ошибок
            with self._lock:
                if any(not item.internal for item in batch):
                    self._total_errors += 1
                    incrementCoreSystemStatsMetric(
                        "batch_total_errors",
                        1,
                        description="Total external batch write errors",
                        source=SYSTEM_STATS_SOURCE,
                    )
                else:
                    self._total_internal_errors += 1
                self._last_error = error_msg
                self._last_error_time = get_now_to_utc()
                self._append_flush_history(
                    duration_seconds=execution_time,
                    batch_size=batch_size,
                    values_count=0,
                    history_count=0,
                    success=False,
                    error=error_msg,
                )
        finally:
            flushBufferedCoreSystemStatsMetrics()

    def shutdown(self, wait: bool = True):
        """Корректное завершение работы батчера"""
        self._stop_event.set()
        # Принудительно записываем оставшиеся данные
        self.flush()
        # Ждем завершения всех задач записи
        if wait:
            # Даем время на завершение текущей записи
            time.sleep(0.1)
            # Выполняем финальную запись синхронно, если есть данные
            with self._lock:
                if self._batch:
                    batch = self._batch[:]
                    self._batch.clear()
                else:
                    batch = []
            if batch:
                self._flush_internal()
        # Ждем завершения фонового потока
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
    
    def get_stats(self):
        """Возвращает статистику работы батчера"""
        with self._lock:
            current_batch_size = len(self._batch)
            flush_history = list(self._flush_history)
            successful_durations = [
                entry["duration_seconds"]
                for entry in flush_history
                if entry.get("success") and entry.get("batch_size", 0) > 0
            ]
            avg_flush_time = sum(successful_durations) / len(successful_durations) if successful_durations else 0
            min_flush_time = min(successful_durations) if successful_durations else 0
            max_flush_time = max(successful_durations) if successful_durations else 0

            ext_added = self._total_added - self._total_internal_added
            ext_values = self._total_values_updated - self._total_internal_values_updated
            ext_history = self._total_history_inserted - self._total_internal_history_inserted
            ext_flushed = max(self._total_flushed, 1)
            ext_errors = self._total_errors

            return {
                "flush_interval": self.flush_interval,
                "current_batch_size": current_batch_size,
                "worker_thread_alive": self._worker_thread.is_alive() if self._worker_thread else False,
                "total_added": self._total_added,
                "total_flushed": self._total_flushed,
                "total_values_updated": self._total_values_updated,
                "total_history_inserted": self._total_history_inserted,
                "total_errors": self._total_errors,
                "total_internal_errors": self._total_internal_errors,
                "last_flush_time": convert_utc_to_local(self._last_flush_time).isoformat() if self._last_flush_time else None,
                "last_error": self._last_error,
                "last_error_time": convert_utc_to_local(self._last_error_time).isoformat() if self._last_error_time else None,
                "execution_time": {
                    "avg_seconds": round(avg_flush_time, 4),
                    "min_seconds": round(min_flush_time, 4),
                    "max_seconds": round(max_flush_time, 4),
                    "count": len(flush_history)
                },
                "flush_history": flush_history,
                "efficiency": {
                    "avg_batch_size": round(ext_added / ext_flushed, 2) if self._total_flushed > 0 else 0,
                    "error_rate": round((ext_errors / ext_flushed * 100), 2) if self._total_flushed > 0 else 0
                },
                "external": {
                    "total_added": ext_added,
                    "total_values_updated": ext_values,
                    "total_history_inserted": ext_history,
                    "total_errors": ext_errors,
                }
            }


# Глобальный экземпляр батчера
_batch_writer = BatchWriter(flush_interval=Config.BATCH_WRITER_FLUSH_INTERVAL)


def shutdown_batch_writer():
    """Функция для корректного завершения работы батчера при остановке приложения"""
    _batch_writer.shutdown(wait=True)


class TypeOperation(Enum):
    """ Type operation """
    Get = "get"
    Set = "set"
    Call = "call"
    Edit = "edit"

_USERS_ADMIN_SET_PROPERTIES = frozenset({
    'role', 'password', 'apikey', 'home_page', 'timezone', 'image', 'lastLogin',
})

class PropertyManager():
    """
    Initializes an ObjectManager instance with the given parameters.

    Args:
        object_id (int): The ID of the object.
        property (Property): The property object containing property details.
        value (Value): The value object containing value details or None.

    Attributes:
        property_id: ID of the property.
        value_id: ID of the value if exists, otherwise None.
        name: Name of the property.
        description: Description of the property.
        object_id: ID of the object.
        history: History count of the property or 0 if not specified.
        changed: Timestamp when the value was changed, None if no value.
        method: Method associated with the property (initialized to None).
        linked: List of linked items if exists, None otherwise.
        source: Source of the value if exists, None otherwise.
        __value: Decoded value of the property.
        type: Type of the property.
        count_read: Count of read operations (initialized to 0).
        count_write: Count of write operations (initialized to 0).
        readed: Timestamp of when the property was last read (UTC).
    """
    def __init__(self, object_id:int, property: Property, value: Value):
        self.property_id = property.id
        self.value_id = value.id if value else None
        self.name = property.name
        self.description = property.description
        self.object_id = object_id
        self.history = property.history or 0
        self.changed = value.changed if value else None
        self.method = None
        self.linked = None
        self.source = value.source if value else None
        if value and value.linked:
            links = value.linked.split(',')
            self.linked = links
        self.__value = None
        self.type = property.type
        self.params = None
        # Parse params from JSON if exists
        if property.params:
            try:
                self.params = json.loads(property.params) if isinstance(property.params, str) else property.params
            except:
                self.params = None
        
        # Extract common parameters
        self.icon = None
        self.color = None
        self.sort_order = None
        self.default_value = None
        self.read_only = False
        
        if self.params and isinstance(self.params, dict):
            self.icon = self.params.get('icon')
            self.color = self.params.get('color')
            self.sort_order = self.params.get('sort_order')
            self.default_value = self.params.get('default_value')
            self.read_only = self.params.get('read_only', False)
        
        if value:
            self.__value = self._decodeValue(value.value, True)
        # Note: if value is None (no record in DB), default_value will be used in getValue()
            
        self.count_read = 0
        self.count_write = 0
        self.readed = get_now_to_utc()

    def _get_color_scales(self):
        return {
            "hue_scale": self.params.get("hue_scale", 360) if self.params else 360,
            "sat_scale": self.params.get("sat_scale", 100) if self.params else 100,
            "color_temp_unit": self.params.get("color_temp_unit", "kelvin") if self.params else "kelvin",
        }

    def _get_color_read_format(self):
        if self.params and self.params.get("read_format"):
            return str(self.params.get("read_format")).lower()
        return "canonical"

    def _ensure_universal_color(self, value):
        """Приводит legacy/строковое значение к универсальному dict для type=color."""
        if value is None or value == "None" or value == "":
            return None
        if isinstance(value, dict):
            try:
                return to_universal_color(value)
            except Exception:
                return value
        try:
            return decode_color_value(value)
        except Exception:
            parsed_color = parse_color_value(value, write_format="auto", scales=self._get_color_scales())
            return to_universal_color(parsed_color)

    def _color_to_output(self, value, read_format=None):
        if value is None:
            return None
        if isinstance(value, str) or (isinstance(value, dict) and "rgb" not in value and "xy" not in value):
            value = self._ensure_universal_color(value)
        target_format = (read_format or self._get_color_read_format() or "canonical").lower()
        return from_universal_color(value, target_format, scales=self._get_color_scales())

    def getColorValue(self, read_format=None):
        return self._color_to_output(self.__value, read_format=read_format)

    def _format_output_value(self, value):
        """Форматирует внутреннее значение для выдачи наружу (get/history)."""
        if value is None:
            return None
        if self.type == 'color':
            return self._color_to_output(value)
        if self.type == 'datetime':
            try:
                return convert_utc_to_local(value)
            except Exception as ex:
                _logger.exception(ex)
        return value

    def _decodeValue(self, value, init=False):
        if value is None:
            return None
        converted_value = None
        # Конвертация строки в указанный тип
        try:
            if value == 'None':
                converted_value = None
            elif self.type == "int":
                if value != '':
                    try:
                        converted_value = int(value)
                    except ValueError:
                        if init:
                            try:
                                converted_value = int(float(value))
                            except (TypeError, ValueError):
                                _logger.warning(
                                    f"Error parsing int during initialization (object_id={self.object_id}, name={self.name}, value={value})",
                                    exc_info=True,
                                )
                                converted_value = value
                        else:
                            raise
                    # Validate min/max if specified
                    if not init and self.params:
                        min_val = self.params.get('min')
                        max_val = self.params.get('max')
                        if min_val is not None and converted_value < min_val:
                            raise ValueError(f"Value {converted_value} is less than minimum {min_val}")
                        if max_val is not None and converted_value > max_val:
                            raise ValueError(f"Value {converted_value} is greater than maximum {max_val}")
                        # Validate step/discreteness if specified
                        if 'step' in self.params:
                            step = self.params['step']
                            if step > 0:
                                base = self.params.get('min', 0)
                                if (converted_value - base) % step != 0:
                                    raise ValueError(
                                        f"Value {converted_value} is not aligned with step {step} "
                                        f"(base: {base}). Allowed values: {base}, {base+step}, {base+2*step}..."
                                    )
                else:
                    converted_value = None
            elif self.type == "float":
                if value != '':
                    converted_value = float(value)
                    # Apply decimals rounding if specified
                    if self.params and 'decimals' in self.params:
                        decimals = int(self.params['decimals'])
                        converted_value = round(converted_value, decimals)
                    # Validate min/max if specified
                    if not init and self.params:
                        min_val = self.params.get('min')
                        max_val = self.params.get('max')
                        if min_val is not None and converted_value < float(min_val):
                            raise ValueError(f"Value {converted_value} is less than minimum {min_val}")
                        if max_val is not None and converted_value > float(max_val):
                            raise ValueError(f"Value {converted_value} is greater than maximum {max_val}")
                        # Validate step/discreteness if specified
                        if 'step' in self.params:
                            step = float(self.params['step'])
                            if step > 0:
                                base = float(self.params.get('min', 0.0))
                                remainder = abs((converted_value - base) % step)
                                # Account for floating point precision errors
                                if remainder > 1e-9 and abs(remainder - step) > 1e-9:
                                    raise ValueError(
                                        f"Value {converted_value} is not aligned with step {step} (base: {base})"
                                    )
                else:
                    converted_value = None
            elif self.type == "str":
                converted_value = value
                # Validate regexp if specified
                if not init and self.params and 'regexp' in self.params:
                    import re
                    pattern = self.params['regexp']
                    if not re.match(pattern, str(converted_value)):
                        raise ValueError(f"Value '{converted_value}' does not match pattern '{pattern}'")
            elif self.type == "datetime":
                if isinstance(value, str):
                    converted_value = parser.parse(value)
                else:
                    converted_value = value
                if converted_value and not init:
                    converted_value = convert_local_to_utc(converted_value)
            elif self.type == "dict":
                if isinstance(value, dict):
                    converted_value = value
                else:
                    converted_value = json.loads(value)
            elif self.type == "list":
                if isinstance(value, list):
                    converted_value = value
                else:
                    converted_value = json.loads(value)
            elif self.type == "bool":
                if isinstance(value, str):
                    if value.lower() in ['true', '1', 't', 'y', 'yes', 'on']:
                        converted_value = True
                    elif value.lower() in ['false', '0', 'f', 'n', 'no', 'off']:
                        converted_value = False
                    else:
                        raise ValueError(f"Invalid boolean value: {value}")
                else:
                    converted_value = bool(value)
            elif self.type == "enum":
                # For enum, validate against allowed values
                converted_value = value
                if not init and self.params and 'enum_values' in self.params:
                    enum_values = self.params['enum_values']
                    if enum_values and isinstance(enum_values, dict):
                        if str(converted_value) not in enum_values:
                            raise ValueError(f"Value '{converted_value}' is not in allowed enum values: {list(enum_values.keys())}")
                    else:
                        _logger.warning(f"Property {self.name}: enum_values is not a dict or empty")
            elif self.type == "color":
                if init:
                    converted_value = self._ensure_universal_color(value)
                else:
                    write_format = "auto"
                    if self.params and self.params.get("write_format"):
                        write_format = str(self.params.get("write_format")).lower()
                    if write_format != "auto":
                        detected = detect_color_format(value)
                        if detected not in ("canonical", write_format):
                            raise ValueError(
                                f"Color write format mismatch for '{self.name}': expected '{write_format}', got '{detected}'"
                            )
                    parsed_color = parse_color_value(value, write_format=write_format, scales=self._get_color_scales())
                    if not init and self.__value not in (None, 'None', ''):
                        try:
                            existing_color = self._ensure_universal_color(self.__value)
                            parsed_color = merge_xy_luminance(parsed_color, existing_color)
                        except Exception:
                            pass
                    converted_value = to_universal_color(parsed_color)
            else:
                converted_value = value
            
            # Universal validation - allowed_values (works for any type except enum which has enum_values)
            if not init and self.params and 'allowed_values' in self.params and self.type != 'enum':
                allowed = self.params['allowed_values']
                if not isinstance(allowed, list):
                    _logger.warning(f"Property {self.name}: allowed_values must be a list, got {type(allowed)}")
                else:
                    # For numeric/bool types, compare values directly
                    if self.type in ['int', 'float', 'bool']:
                        if converted_value not in allowed:
                            raise ValueError(
                                f"Value {converted_value} is not in allowed values: {allowed}"
                            )
                    else:
                        # For string-like types and others, compare as strings
                        if str(converted_value) not in [str(v) for v in allowed]:
                            raise ValueError(
                                f"Value '{converted_value}' is not in allowed values: {allowed}"
                            )
        except (ParserError, json.JSONDecodeError) as ex:
            # Parsing errors (datetime, JSON) should be handled gracefully during init
            if init and self.type == "color":
                try:
                    converted_value = self._ensure_universal_color(value)
                except Exception as color_ex:
                    _logger.warning(
                        f"Error parsing color during initialization (object_id={self.object_id}, name={self.name}, value={value}): {color_ex}",
                        exc_info=True,
                    )
                    converted_value = value
            elif init:
                _logger.warning(
                    f"Error parsing value during initialization (object_id={self.object_id}, name={self.name}, type={self.type}, value={value}): {str(ex)}",
                    exc_info=True
                )
                # During initialization, return the original value if parsing fails
                converted_value = value
            else:
                # During set operations, raise the exception to prevent invalid values
                _logger.error(
                    f"Error parsing value (object_id={self.object_id}, name={self.name}, type={self.type}, value={value}): {str(ex)}",
                    exc_info=True
                )
                raise ValueError(f"Failed to parse value '{value}' for property '{self.name}': {str(ex)}") from ex
        except ValueError as ex:
            if init:
                _logger.warning(
                    f"Error validating value during initialization (object_id={self.object_id}, name={self.name}, type={self.type}, value={value}): {str(ex)}",
                    exc_info=True,
                )
                converted_value = value
            else:
                raise
        except Exception as ex:
            # Other errors (parsing, type conversion) are logged but we don't want to silently fail
            # If init=True, we might want to be more lenient (e.g., during initialization from DB)
            if init and self.type == "color":
                try:
                    converted_value = self._ensure_universal_color(value)
                except Exception as color_ex:
                    _logger.warning(
                        f"Error decoding color during initialization (object_id={self.object_id}, name={self.name}, value={value}): {color_ex}",
                        exc_info=True,
                    )
                    converted_value = value
            elif init:
                _logger.warning(
                    f"Error decoding value during initialization (object_id={self.object_id}, name={self.name}, value={value}): {str(ex)}",
                    exc_info=True
                )
                # During initialization, return the original value if conversion fails
                converted_value = value
            else:
                # During set operations, raise the exception to prevent invalid values
                _logger.error(
                    f"Error decoding value (object_id={self.object_id}, name={self.name}, value={value}): {str(ex)}",
                    exc_info=True
                )
                raise ValueError(f"Failed to decode value '{value}' for property '{self.name}': {str(ex)}") from ex
        return converted_value

    def _encodeValue(self, value=None):
        # convert to string
        if value is None:
            value = self.__value
        if value is None:
            return 'None'
        try:
            if self.type == "int":
                return str(value)
            elif self.type == "float":
                return str(value)
            elif self.type == "str":
                return str(value)
            elif self.type == "datetime":
                return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            elif self.type == "dict":
                return json.dumps(value)
            elif self.type == "list":
                return json.dumps(value)
            elif self.type == "enum":
                return str(value)
            elif self.type == "color":
                return encode_color_value(value)
            else:
                return value
        except Exception as ex:
            _logger.exception(ex, exc_info=True)
        return str(value)

    def _saveValue(self, save_history:bool=None, history_only:bool=False, history_changed:datetime.datetime=None, history_source:str=None, history_value=None, explicit_date:bool=False):
        if self.value_id is None:
            with session_scope() as session:
                valRec = Value()
                valRec.object_id = self.object_id
                valRec.name = self.name
                session.add(valRec)
                session.commit()
                self.value_id = valRec.id

        if history_only:
            # Режим только истории - используем переданные параметры
            stringValue = self._encodeValue(history_value) if history_value is not None else 'None'
            changed_dt = history_changed
            source_str = history_source or ''
        else:
            # Обычный режим - используем текущие значения
            stringValue = self._encodeValue()
            changed_dt = self.changed
            source_str = self.source

        # Определяем, нужно ли сохранять историю
        should_save_history = False
        if (self.history > 0 and (save_history is None or save_history)) or \
           (self.history < 0 and save_history is not None and save_history):
            should_save_history = True

        is_internal = (source_str == SYSTEM_STATS_SOURCE)

        value_update = ValueUpdate(
            value_id=self.value_id,
            value=stringValue,
            changed=changed_dt,
            source=source_str,
            save_history=should_save_history,
            history_value=stringValue if should_save_history else None,
            history_only=history_only,
            explicit_date=explicit_date,
            internal=is_internal
        )

        # Добавляем в батчер (асинхронная запись)
        _batch_writer.add(value_update)

    def cleanHistory(self):
        with session_scope() as session:
            count = session.query(History).where(History.value_id == self.value_id).count()
            if (self.history != 0):
                period = abs(self.history)
                # clean history
                dt = get_now_to_utc() - datetime.timedelta(days=period)
                sql = delete(History).where(History.value_id == self.value_id, History.added < dt)
                result = session.execute(sql)
                deleted_count = result.rowcount
                session.commit()
                return deleted_count, count - deleted_count
            elif count > 0:
                sql = delete(History).where(History.value_id == self.value_id)
                result = session.execute(sql)
                deleted_count = result.rowcount
                session.commit()
                return deleted_count, count - deleted_count
            return 0, count

    def setValue(self, value, source='', changed=None, save_history:bool=None, bypass_rate_limit:bool=False, track_stats:bool=True):
        # Check if property is read-only
        if self.read_only:
            raise PermissionError(f"Property '{self.name}' is read-only and cannot be modified")
        
        # Определяем дату для установки значения
        if changed is not None:
            new_changed = changed
            # Нормализуем дату к наивному UTC для сравнения
            if new_changed.tzinfo is not None:
                from zoneinfo import ZoneInfo
                new_changed = new_changed.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        else:
            new_changed = get_now_to_utc()
        
        # Проверяем, нужно ли обновлять значение или только историю
        # Если указана дата и она старше текущей даты значения, обновляем только историю
        history_only = False
        if changed is not None and self.changed is not None:
            # Нормализуем self.changed для сравнения (если есть таймзона)
            compare_changed = self.changed
            if compare_changed.tzinfo is not None:
                from zoneinfo import ZoneInfo
                compare_changed = compare_changed.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            if new_changed < compare_changed:
                history_only = True
        
        # Подготавливаем значения для истории (нужны в любом случае)
        temp_value = self._decodeValue(value)
        temp_source = source
        username = getattr(current_user, 'username', None)
        if username:
            if temp_source != '':
                temp_source += ':'
            temp_source += username
        
        # Если не history_only, проверяем rate limit и обновляем значение
        if not history_only:
            # Check rate limit
            if self.params and 'rate_limit' in self.params and not bypass_rate_limit:
                rate_limit = float(self.params['rate_limit'])
                if rate_limit > 0 and self.changed:
                    time_since_last = (get_now_to_utc() - self.changed).total_seconds()
                    if time_since_last < rate_limit:
                        remaining = rate_limit - time_since_last
                        raise ValueError(
                            f"Property '{self.name}' can be changed only once per {rate_limit} seconds. "
                            f"Please wait {remaining:.1f} more seconds."
                        )

            self.__value = temp_value
            self.source = temp_source
            self.changed = new_changed

        # save Value To DB
        try:
            if history_only:
                # Сохраняем только историю с указанной датой
                # Если changed был указан явно, explicit_date=True
                self._saveValue(save_history, history_only=True, history_changed=new_changed, history_source=temp_source, history_value=temp_value, explicit_date=(changed is not None))
            else:
                # Если changed был указан явно, explicit_date=True
                self._saveValue(save_history, explicit_date=(changed is not None))
        except Exception as ex:
            _logger.exception(ex, exc_info=True)

        if not history_only and track_stats:
            self.count_write = self.count_write + 1
            if not (self.params and self.params.get("internal")):
                incrementCoreSystemStatsMetric(
                    "property_writes",
                    1,
                    description="Total property writes (event-driven)",
                    source=SYSTEM_STATS_SOURCE,
                )

    def getValue(self, track_stats:bool=True):
        if track_stats:
            self.readed = get_now_to_utc()
            self.count_read = self.count_read + 1
            if not (self.params and self.params.get("internal")):
                incrementCoreSystemStatsMetric(
                    "property_reads",
                    1,
                    description="Total property reads (event-driven)",
                    source=SYSTEM_STATS_SOURCE,
                )

        if self.__value is None and self.default_value is not None:
            # Decode default_value with the same logic as regular value
            try:
                return self._decodeValue(str(self.default_value), init=True)
            except Exception as ex:
                _logger.error(f"Error decoding default_value for {self.name}: {ex}")
                return self.default_value

        return self._format_output_value(self.__value)

    @property
    def value(self):
        return self.getValue()

    @value.setter
    def value(self, value):
        self.setValue(value)

    def bindMethod(self, name):
        self.method = name

    def to_dict(self):
        result = {
            "property_id": self.property_id,
            "value_id": self.value_id,
            "name": self.name,
            "description": self.description,
            "history": self.history,
            "changed": str(convert_utc_to_local(self.changed)) if self.changed else None,
            "method": self.method,
            "linked": self.linked,
            "source": self.source,
            "type": self.type,
            "value": self.value if self.type != 'datetime' else str(self.value),
            "count_read": self.count_read,
            "count_write": self.count_write,
            "readed": str(convert_utc_to_local(self.readed))
        }
        
        # Add common parameters
        if self.icon:
            result["icon"] = self.icon
        if self.color:
            result["color"] = self.color
        if self.sort_order is not None:
            result["sort_order"] = self.sort_order
        if self.read_only:
            result["read_only"] = self.read_only
        
        # Add params for enum type
        if self.type == 'enum' and self.params and 'enum_values' in self.params:
            enum_values = self.params['enum_values']
            if enum_values and isinstance(enum_values, dict):
                result["enum_values"] = enum_values
                # Add text description if available
                if self.value and str(self.value) in enum_values:
                    result["text"] = enum_values[str(self.value)]
        
        # Add validation parameters
        if self.params:
            if 'min' in self.params:
                result["min"] = self.params['min']
            if 'max' in self.params:
                result["max"] = self.params['max']
            if 'decimals' in self.params:
                result["decimals"] = self.params['decimals']
            if 'regexp' in self.params:
                result["regexp"] = self.params['regexp']
            if 'step' in self.params:
                result["step"] = self.params['step']
            if 'allowed_values' in self.params:
                result["allowed_values"] = self.params['allowed_values']
            if 'rate_limit' in self.params:
                result["rate_limit"] = self.params['rate_limit']
            if 'depends_on' in self.params:
                result["depends_on"] = self.params['depends_on']
            if self.type == 'color':
                if 'read_format' in self.params:
                    result["read_format"] = self.params['read_format']
                if 'write_format' in self.params:
                    result["write_format"] = self.params['write_format']
                if 'color_temp_unit' in self.params:
                    result["color_temp_unit"] = self.params['color_temp_unit']
                if 'hue_scale' in self.params:
                    result["hue_scale"] = self.params['hue_scale']
                if 'sat_scale' in self.params:
                    result["sat_scale"] = self.params['sat_scale']
        
        return result

    def __str__(self):
        return f"PropertyManager(name='{self.name}', description='{self.description}', value='{self.value}')"

    def __repr__(self):
        return self.__str__()


"""
Manages method information and execution tracking.

This class encapsulates information about methods, including their execution status and results.
It provides methods to convert the method data to a dictionary and string representations.

Attributes:
    methods (list): List of method dictionaries including parent methods.
    name (str): Name of the method (taken from the first method in the list).
    description (str): Description of the method (taken from the first method in the list).
    source (str): Source of the method (None by default).
    count_executed (int): Number of times the method has been executed.
    executed (datetime): Timestamp of last execution (None if never executed).
    exec_params (any): Parameters used in last execution.
    exec_result (any): Result from last execution.
    exec_time (int): Time taken for last execution (in milliseconds).
"""
class MethodManager():
    def __init__(self, methods):
        self.methods = methods  # include parents
        self.name = methods[0]["name"]
        self.description = methods[0]["description"]
        self.source = None
        self.count_executed = 0
        self.executed = None
        self.exec_params = None
        self.exec_result = None
        self.exec_time = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "methods": self.methods,
            "count_executed": self.count_executed,
            "executed": str(convert_utc_to_local(self.executed)) if self.executed else None,
            "exec_params": self.exec_params,
            "exec_result": self.exec_result,
            "exec_time": self.exec_time
        }

    def __str__(self):
        return f"MethodManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()


"""
Manages object properties and methods with permission control.

This class provides functionality to handle object properties and methods with
built-in permission checking. It maintains properties and methods dictionaries,
handles property value updates with history tracking, and performs permission
checks before allowing any operations.

Attributes:
    object_id: The ID of the managed object.
    name: The name of the managed object.
    description: Description of the managed object.
    properties: Dictionary of property managers.
    methods: Dictionary of method managers.
"""
class ObjectManager:
    """ 
        Object manager

        Contain properties and methods
    """
    def __init__(self, obj: Object):
        object.__setattr__(self, "__inited", False)
        object.__setattr__(self, "__permissions", None)
        object.__setattr__(self, "__templates", {})
        object.__setattr__(self, "_current_execution_source", None)
        object.__setattr__(self, "_runtime", {})
        object.__setattr__(self, "_lifecycle_running", False)
        object.__setattr__(self, "_render_env", None)
        object.__setattr__(self, "_render_template_name", None)
        object.__setattr__(self, "_render_template", None)
        self.object_id = obj.id
        self.name = obj.name
        self.description = obj.description
        # Create logger adapter with object name context
        self._logger = ObjectLoggerAdapter(_logger, {'object_name': self.name})
        self.properties = {}
        self.methods = {}

    @property
    def runtime(self) -> dict:
        return object.__getattribute__(self, "_runtime")

    def clear_runtime(self) -> None:
        object.__getattribute__(self, "_runtime").clear()

    def _record_reactive_loop(self, chain: str) -> None:
        self._runtime["last_reactive_loop"] = {
            "chain": chain,
            "at": str(get_now_to_utc()),
        }
        from app.core.main.ObjectsStorage import objects_storage
        objects_storage.reactive_loop_count += 1
        incrementCoreSystemStatsMetric(
            "reactive_loops",
            1,
            description="Reactive loop counter",
            source=SYSTEM_STATS_SOURCE,
        )
        self._logger.error("[ReactiveLoop] %s", chain)
        if Config.REACTIVE_LOOP_NOTIFY:
            addNotify(
                name=f"reactive_loop:{self.name}",
                description=chain,
                category=CategoryNotify.Warning,
                source="Objects",
            )

    def _addProperty(self, property: PropertyManager) -> None:
        if property.value_id is None:
            with session_scope() as session:
                valRec = Value()
                valRec.object_id = property.object_id
                valRec.name = property.name
                session.add(valRec)
                session.commit()
                property.value_id = valRec.id
        self.properties[property.name] = property

    def set_permission(self, permissions):
        object.__setattr__(self, "__permissions", permissions)
        object.__setattr__(self, "__inited", True)

    def _check_permissions(self, operation:TypeOperation, property_name:str=None, method_name:str=None):
        if not object.__getattribute__(self, "__inited"):
            return True

        name = object.__getattribute__(self, "name")

        if name == "_permissions" and operation == TypeOperation.Get:
            return True

        # permissions check
        username = getattr(current_user, 'username', None)
        if username is None:
            return True

        role = getattr(current_user, 'role', None)

        if role == 'root':
            return True

        if property_name and 'Users' in getattr(self, 'parents', []):
            if property_name == 'password' and operation == TypeOperation.Get:
                raise PermissionError(
                    f"User {username}({role}) don't have permission to {operation.name} "
                    f"obj:{name} property:{property_name} (sensitive)"
                )
            if operation == TypeOperation.Set and role == 'admin':
                if property_name in _USERS_ADMIN_SET_PROPERTIES:
                    return True
            if property_name == 'password' and operation == TypeOperation.Set and role != 'admin':
                raise PermissionError(
                    f"User {username}({role}) don't have permission to {operation.name} "
                    f"obj:{name} property:{property_name} (sensitive)"
                )
            if property_name == 'apikey' and operation in (TypeOperation.Get, TypeOperation.Set):
                if role != 'admin' and username != name:
                    raise PermissionError(
                        f"User {username}({role}) don't have permission to {operation.name} "
                        f"obj:{name} property:{property_name} (sensitive)"
                    )

        _permissions = object.__getattribute__(self, "__permissions")
        if _permissions is None:
            if role in ["user","editor","admin"]:
                return True
            else:
                raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:None")

        permissions = None

        if "self" in _permissions:
            permissions = _permissions["self"]

        if property_name:
            if "properties" in _permissions and property_name in _permissions["properties"]:
                permissions = _permissions["properties"][property_name]

        if method_name:
            if "methods" in _permissions and method_name in _permissions["methods"]:
                permissions = _permissions["methods"][method_name]

        if permissions:
            permissions = permissions.get(operation.value, None)

        if permissions:
            denied_users = permissions.get("denied_users",None)
            if denied_users:
                if username in denied_users or "*" in denied_users:
                    raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")
            access_users = permissions.get("access_users",None)
            if access_users:
                if username in access_users or "*" in access_users:
                    return True
            denied_roles = permissions.get("denied_roles",None)
            if denied_roles:
                if role in denied_roles or "*" in denied_roles:
                    raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")
            access_roles = permissions.get("access_roles",None)
            if access_roles:
                if role in access_roles or "*" in access_roles:
                    return True

        if role in ["user","editor","admin"]:
            return True

        raise PermissionError(f"User {username}({role}) don't have permission to {operation.name} obj:{name} property:{property_name} method:{method_name} permissions:{json.dumps(permissions)}")

    def _validate_dependencies(self, property_name: str, new_value, depends_on):
        """
        Validate property dependencies before setting value
        
        Args:
            property_name: Name of the property being set
            new_value: New value to set
            depends_on: Dependency configuration
            
        Format examples:
        1. Simple: {"property": "mode", "value": "manual"}
        2. Condition: {"property": "enabled", "value": True, "condition": "equals"}
        3. Multiple: [
            {"property": "mode", "value": "manual"},
            {"property": "enabled", "value": True}
        ]
        4. Complex: {
            "property": "temperature",
            "condition": "greater_than",
            "value": 0,
            "error_message": "Temperature must be positive when heating is on"
        }
        """
        # Handle list of dependencies
        if isinstance(depends_on, list):
            for dep in depends_on:
                self._validate_single_dependency(property_name, new_value, dep)
            return
        
        # Handle single dependency
        self._validate_single_dependency(property_name, new_value, depends_on)

    def _validate_single_dependency(self, property_name: str, new_value, dependency: dict):
        """Validate a single dependency"""
        if not isinstance(dependency, dict):
            self._logger.warning(f"Dependency for {property_name} must be a dict, got {type(dependency)}")
            return
        
        dep_property = dependency.get('property')
        dep_value = dependency.get('value')
        condition = dependency.get('condition', 'equals')
        error_message = dependency.get('error_message')
        
        if not dep_property:
            self._logger.warning(f"Dependency for {property_name} is missing 'property' field")
            return
        
        if dep_property not in self.properties:
            self._logger.warning(f"Dependency property '{dep_property}' not found for {property_name}")
            return
        
        current_dep_value = self.getProperty(dep_property)
        
        # Check condition
        is_valid = False
        try:
            if condition == 'equals':
                is_valid = current_dep_value == dep_value
            elif condition == 'not_equals':
                is_valid = current_dep_value != dep_value
            elif condition == 'greater_than':
                is_valid = current_dep_value > dep_value
            elif condition == 'less_than':
                is_valid = current_dep_value < dep_value
            elif condition == 'greater_or_equal':
                is_valid = current_dep_value >= dep_value
            elif condition == 'less_or_equal':
                is_valid = current_dep_value <= dep_value
            elif condition == 'in':
                is_valid = current_dep_value in dep_value
            elif condition == 'not_in':
                is_valid = current_dep_value not in dep_value
            else:
                self._logger.warning(f"Unknown condition '{condition}' in dependency for {property_name}")
                return
        except Exception as e:
            self._logger.warning(f"Error checking dependency condition for {property_name}: {e}")
            return
        
        if not is_valid:
            if error_message:
                raise ValueError(error_message)
            else:
                raise ValueError(
                    f"Cannot set '{property_name}' to '{new_value}': "
                    f"depends on '{dep_property}' {condition} '{dep_value}', "
                    f"but current value is '{current_dep_value}'"
                )

    def setProperty(self, name:str, value, source:str='', save_history:bool=None, changed:datetime.datetime=None, track_stats:bool=True):
        """ Set property value

        Args:
            name (str): property name
            value (str): property value
            source (str): source of the value
            save_history (bool): save history of the value (default is None)
            changed (datetime.datetime, optional): Date/time for the value. Used when saving history. Defaults to None (current time).
            track_stats (bool): increment count_write/count_read counters

        Returns:
            bool: Result
        """
        try:
            self._logger.debug("ObjectManager::setProperty %s.%s - %s", self.name, name, str(value))
            self._check_permissions(TypeOperation.Set, name, None)

            if name not in self.properties:
                with session_scope() as session:
                    property_db = Property()
                    property_db.object_id = self.object_id
                    property_db.name = name
                    property_db.type = type(value).__name__
                    session.add(property_db)
                    session.commit()
                    prop = PropertyManager(self.object_id, property_db, None)
                    self._addProperty(prop)
            prop = self.properties[name]
            
            # Check dependencies before setting value
            if prop.params and 'depends_on' in prop.params:
                self._validate_dependencies(name, value, prop.params['depends_on'])

            if not chain_enter(self.name, name):
                self._record_reactive_loop(chain_format())
                return False

            try:
                old = prop.getValue()
                if source is None or source == '':
                    if self._current_execution_source is not None:
                        source = self._current_execution_source
                prop.setValue(value, source, changed=changed, save_history=save_history, track_stats=track_stats)
                value = prop.getValue()
                if prop.method:
                    args = {
                        'VALUE': value, 'NEW_VALUE': value, 'OLD_VALUE': old, 'PROPERTY': name, 'SOURCE': source,
                    }
                    self.callMethod(prop.method, args, source)
            finally:
                chain_exit()

            is_system_stats_write = (
                self.name == SYSTEM_STATS_OBJECT
                or str(source or "").startswith(SYSTEM_STATS_SOURCE)
            )

            # link
            if prop.linked and not is_system_stats_write:
                for link in prop.linked:
                    if link == source:
                        continue
                    # get plugin
                    plugin = getModule(link)
                    if plugin:
                        try:
                            # def task_wrapper(plugin, object_name, property_name, property_value):
                            #     def wrapper():
                            #         plugin.changeLinkedProperty(object_name, property_name, property_value)
                            #     return wrapper

                            # _poolLinkedProperty.submit(task_wrapper(plugin, self.name, name, value), task_id=f"{self.name, name}")

                            _poolLinkedProperty.submit(
                                plugin.changeLinkedProperty,
                                f"{link}_{self.name}.{name}",
                                link,
                                self.name,
                                name,
                                value
                            )
                        except Exception as e:
                            _logger.exception(e)

            # send event to proxy
            if is_system_stats_write:
                # Keep WebSocket updates for SystemStats subscriptions, but
                # skip generic proxy fan-out to avoid thread-pool overload.
                scheduleSystemStatsWsNotify(self.name, name, value)
            else:
                plugins = getModulesByAction("proxy")
                for plugin in plugins:
                    try:
                        # def task_wrapper(plugin, object_name, property_name, property_value):
                        #     def wrapper():
                        #         plugin.changeProperty(object_name, property_name, property_value)
                        #     return wrapper
                        # _poolLinkedProperty.submit(task_wrapper(plugin, self.name, name, value), task_id=f"proxy_{self.name, name}")
                        _poolLinkedProperty.submit(
                            plugin.changeProperty,
                            f"proxy_{plugin.name}_{self.name}.{name}",
                            f"proxy:{plugin.name}",
                            self.name,
                            name,
                            value,
                            ignore_owner_limit=True,
                        )

                    except Exception as e:
                        _logger.exception(e)
            if self.name == "SystemVar" and name == "system_stats":
                invalidateSystemStatsEnabledCache()
            return True
        except (ValueError, PermissionError) as ex:
            # Validation errors (constraint violations) should be logged
            # and propagated to callers that want to handle them.
            self._logger.warning(
                "Validation error in setProperty %s.%s: %s",
                self.name,
                name,
                str(ex),
            )
            raise
        except Exception as ex:
            self._logger.exception(ex, exc_info=True)
            return False

    def updateProperty(self, name:str, value, source:str='', track_stats:bool=True) -> bool:
        """Update property

        Args:
            name (str): Name property
            value (_type_): New value
            source (str, optional): Source. Defaults to ''.
            track_stats (bool): increment count_write/count_read counters

        Returns:
            bool: Result
        """

        try:
            # cast value and validate constraints
            oldValue = self.getProperty(name)
            if name in self.properties:
                prop = self.properties[name]
                # Decode and validate value (init=False to enforce constraints)
                value = prop._decodeValue(value, init=False)
                if prop.type == "color":
                    oldValue = prop.getColorValue(read_format="canonical")
            if oldValue != value:
                return self.setProperty(name, value, source, track_stats=track_stats)
            return True
        except ValueError as ex:
            # Validation errors (constraint violations) should be logged and prevent updating the value
            self._logger.warning(f"Validation error in updateProperty {self.name}.{name}: {str(ex)}")
            return False
        except Exception as ex:
            self._logger.exception(ex, exc_info=True)
        return False

    def getProperty(self, name:str, data:str = 'value'):
        """Get value of property

        Args:
            name (str): Name property
            data (str, optional): Data type. Defaults to 'value'. (changed, source, text, icon, color, sort_order, read_only)

        Returns:
            any: Value
        """
        self._check_permissions(TypeOperation.Get, name, None)
        
        if name == 'description':
            return self.description

        if name in self.properties:
            prop = self.properties[name]
            # For enum type, handle 'text' data request
            if data == 'text' and prop.type == 'enum':
                current_value = prop.getValue()
                if current_value and prop.params and 'enum_values' in prop.params:
                    enum_values = prop.params['enum_values']
                    if enum_values and isinstance(enum_values, dict):
                        return enum_values.get(str(current_value), current_value)
                return current_value

            if data == 'enum' and prop.type == 'enum':
                if 'enum_values' in prop.params:
                    enum_values = prop.params['enum_values']
                    return enum_values
                return None

            if prop.type == 'color':
                color_formats = {'canonical', 'xy', 'rgb', 'hex', 'hs', 'hsv', 'hsl', 'hsb', 'color_temp', 'zigbee2mqtt'}
                if data in color_formats:
                    return prop.getColorValue(read_format=data)
                if data == 'value':
                    return prop.getValue()
            
            value = getattr(prop, data, None)
            if data == 'changed' and value:
                try:
                    return convert_utc_to_local(value)
                except Exception as ex:
                    _logger.exception(ex)
            return value
        return None

    def getChanged(self, name:str):
        """Get datetime changing property

        Args:
            name (str): name property

        Returns:
            datetime: Datetime changing property
        """
        return self.getProperty(name, 'changed')

    def __getattr__(self, name):
        if name in self.methods:
            def dynamic_method(args=None, source: str = '') -> str:
                return self.callMethod(name, args=args, source=source)
            return dynamic_method
        if name in self.__dict__['properties']:
            if not self._check_permissions(TypeOperation.Get, name, None):
                raise (f"You don't have permission to get property {name}")
            prop = self.__dict__['properties'][name]
            return prop.value
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name.startswith('_') or name in ('properties', 'methods', 'object_id', 'name', 'description', 'parents'):
            super().__setattr__(name, value)
            return

        self._check_permissions(TypeOperation.Set, name, None)
        self.setProperty(name, value)

    def _addMethod(self, method: MethodManager):
        self.methods[method.name] = method

    def _bindMethod(self, prop_name, method_name):
        if method_name not in self.methods:
            _logger.warning("Method %s does not exist.", method_name)
            return
        self.properties[prop_name].bindMethod(method_name)

    def callMethod(self, name, args=None, source:str = '') -> str:
        """Call a method on the object.
        Args:
            name (str): The name of the method to call.
            args (list): The arguments to pass to the method.
            source (str): The source of the call.
        Returns:
            str: The result of the method call.
        """
        if name not in self.methods:
            _logger.warning("Method %s does not exist.", name)
            return None

        start = time.perf_counter()

        self._check_permissions(TypeOperation.Call, None, name)

        source = source if source else "self." + name
        self._current_execution_source = source
        try:
            variables = {
                'self': self,
                'params': args,
                'logger': _logger,
                'source': source,
                'runtime': self._runtime,
                **vars(self)
            }
            methods = self.methods[name].methods
            output = ''
            method_context = {
                'object': self.name,
                'method': name,
                'owner': None,
                'source': source,
            }
            for method in methods:
                method_context['owner'] = method.get('owner')
                res, error = execute_and_capture_output(
                    method['code'],
                    variables,
                    code_filename=f"<Method:{self.name}.{name}>",
                    method_context=method_context,
                )
                if error:
                    self._logger.error(
                        "Error executing method %s.%s: %s",
                        method['owner'], name, res,
                    )
                    output += "Error method in " + method['owner'] + "\n" + res
                    break
                if res:
                    output += res + "\n"

            username = getattr(current_user, 'username', None)
            if username:
                if source != '':
                    source += ':'
                source += username

            self.methods[name].source = source
            self.methods[name].executed = get_now_to_utc()
            self.methods[name].exec_params = args
            self.methods[name].exec_result = output
            self.methods[name].count_executed = self.methods[name].count_executed + 1
            if self.name != SYSTEM_STATS_OBJECT:
                incrementCoreSystemStatsMetric(
                    "methods_executed",
                    1,
                    description="Total method calls (event-driven)",
                    source=SYSTEM_STATS_SOURCE,
                )

            end = time.perf_counter()
            self.methods[name].exec_time = int((end - start) * 1000)  # в миллисекунды

            # send event to proxy
            plugins = getModulesByAction('proxy')
            for plugin in plugins:
                plugin.executedMethod(self.name, name)

            return output
        except Exception as ex:
            self._logger.exception(ex)
            return str(ex)
        finally:
            self._current_execution_source = None

    def _setTemplates(self, templates):
        object.__setattr__(self, "__templates", templates)
        self._reset_render_cache()

    def _reset_render_cache(self):
        object.__setattr__(self, "_render_env", None)
        object.__setattr__(self, "_render_template_name", None)
        object.__setattr__(self, "_render_template", None)

    def _resolve_render_template_name(self, templates):
        render_template = self.name
        if templates.get(render_template):
            return render_template

        for parent in self.parents:
            if templates.get(parent):
                return parent

        return None

    def has_render_template(self) -> bool:
        templates = object.__getattribute__(self, "__templates")
        return self._resolve_render_template_name(templates) is not None

    def _get_render_template(self, templates):
        template_name = self._resolve_render_template_name(templates)
        if not template_name:
            return None

        cached_template = object.__getattribute__(self, "_render_template")
        cached_template_name = object.__getattribute__(self, "_render_template_name")
        env = object.__getattribute__(self, "_render_env")

        if cached_template is not None and cached_template_name == template_name and env is not None:
            return cached_template

        from jinja2 import Environment, DictLoader
        from app.core.lib.object import getProperty

        env = Environment(loader=DictLoader(templates))
        env.globals.update(getProperty=getProperty)
        template = env.get_template(template_name)

        object.__setattr__(self, "_render_env", env)
        object.__setattr__(self, "_render_template_name", template_name)
        object.__setattr__(self, "_render_template", template)
        return template

    def render(self) -> str:
        """Render object template

        Returns:
            str: html view object
        """
        try:
            templates = object.__getattribute__(self, "__templates")
            template = self._get_render_template(templates)
            result = template.render(object=self) if template else ''
            if result == 'None':
                result = ''
            return result
        except Exception as ex:
            self._logger.error(ex, exc_info=True)
            return str(ex)

    def setPropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Set the value of a Property with a Timeout

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        self._check_permissions(TypeOperation.Set, propName, None)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'setProperty("{self.name}.{propName}","{str(value)}"{src})'
        setTimeout(self.name + "_" + propName + "_timeout", code, timeout)

    def updatePropertyTimeout(self, propName:str, value, timeout:int, source=''):
        """Update property by its name if value changed on timeout.

        Args:
            propName (str): Name property
            value(Any): Value
            timeout(int): Timeout in sec
            source(str): Source
        """
        self._check_permissions(TypeOperation.Set, propName, None)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'updateProperty("{self.name}.{propName}","{str(value)}"{src})'
        setTimeout(self.name + "_" + propName + "_timeout", code, timeout)

    def callMethodTimeout(self, methodName:str, timeout:int, source:str = ''):
        """Call method with a timeout

        Args:
            methodName (str): Name method
            timeout (int): Timeout in sec
            source (str, optional): Source. Defaults to ''.
        """
        self._check_permissions(TypeOperation.Call, None, methodName)

        src = f',"{source}"' if source else ',"Scheduler"'
        code = f'callMethod("{self.name}.{methodName}"{src})'
        setTimeout(self.name + "_" + methodName + "_timeout", code, timeout)

    def getHistory(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, limit:int = None, order_desc: bool = False, func=None) -> list:
        """Get history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin local datetime. Defaults to None.
            dt_end (datetime, optional): End local datetime. Defaults to None.
            limit (int, optional): Limit. Defaults to None.
            order_desc (bool, optional): Order desc. Defaults to False.
            func (function, optional): Function to apply to the data. Defaults to None.

        Returns:
            list: List of history
        """
        self._check_permissions(TypeOperation.Get, name, None)

        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        dt_begin = convert_local_to_utc(dt_begin)
        dt_end = convert_local_to_utc(dt_end)

        with session_scope() as session:
            result = History.getHistory(session, value_id, dt_begin,dt_end,limit,order_desc,row2dict)
            for item in result:
                decoded = prop._decodeValue(item["value"], init=True)
                item['value'] = prop._format_output_value(decoded)
                del item["value_id"]

            from app.core.lib.common import is_datetime_in_range
            if is_datetime_in_range(prop.changed, dt_begin, dt_end, True):
                changed = convert_utc_to_local(prop.changed)
                if result:
                    find = any(item.get("added") == changed for item in result)
                    if not find:
                        result.append({"value": prop.value, "added": changed, "source": prop.source})
                else:
                    result.append({"value": prop.value, "added": changed, "source": prop.source})
            if func:
                result = [func(r) for r in result]
            return result

    def getHistoryAggregate(self, name:str, dt_begin:datetime = None, dt_end:datetime = None, func:str = None):
        """Get aggregate history of a property

        Args:
            name (str): Name property
            dt_begin (datetime, optional): Begin local datetime. Defaults to None.
            dt_end (datetime, optional): End local datetime. Defaults to None.
            func (str, optional): Aggregate function (min,max,sum,avg,count). Defaults to None, return all aggregate value.

        Returns:
            any : Result function
        """
        self._check_permissions(TypeOperation.Get, name, None)

        if name not in self.properties:
            return None
        prop:PropertyManager = self.properties[name]
        value_id = prop.value_id

        with session_scope() as session:
            if func == 'count':
                dt_begin = convert_local_to_utc(dt_begin)
                dt_end = convert_local_to_utc(dt_end)
                result = History.get_count(session, value_id, dt_begin,dt_end)
                return result
            data = self.getHistory(name, dt_begin, dt_end)
            if not data:
                return None
            data = [item['value'] for item in data]
            if func == 'min':
                result = min(data)
            elif func == 'max':
                result = max(data)
            elif func == 'sum':
                result = sum(data)
            elif func == 'avg':
                result = sum(data) / len(data) if data else 0
            else:
                result = {
                    "count": len(data),
                    "min": min(data),
                    "max": max(data),
                    "sum": sum(data),
                    "avg": sum(data) / len(data) if data else 0
                }
            return result

    """
    Cleans the history of all properties in the object manager.

    Iterates over all properties and cleans their history, returning a count of deleted items
    and the remaining history for each property.

    Returns:
        dict: A dictionary with property names as keys and dictionaries as values.
              Each value dictionary contains:
                - "history": The remaining history of the property
                - "deleted": Count of deleted history items
                - "all": Total count of history items (deleted + remaining)
    """
    def cleanHistory(self):
        """Clean history of all properties"""
        count = {}
        for key, prop in self.properties.items():
            res = prop.cleanHistory()
            if res is None:
                # SQLite locked or session_scope swallowed OperationalError
                res = (0, 0)
            deleted_count, all = res
            count[key] = {"history": prop.history, "deleted":deleted_count, "all": all}
        return count

    def getStats(self):
        stat_props = {}
        stat_methods = {}
        for name, prop in self.properties.items():
            from app.core.utilities.strings import truncate_string
            value = truncate_string(str(prop.value), 30)
            stat_props[name] = {
                'id': prop.property_id,
                'description': prop.description,
                'value': value,
                'source': prop.source,
                'count_read': prop.count_read,
                'count_write': prop.count_write,
                'last_read': prop.readed,
                'last_write': prop.changed,
            }
        for name, method in self.methods.items():
            stat_methods[name] = {
                'count_executed': method.count_executed,
                'last_executed': method.executed,
                'exec_time': method.exec_time,
                'source': method.source,
                'params': method.exec_params,
            }
        return {
            "stat_properties": stat_props,
            "stat_methods": stat_methods,
        }

    def to_dict(self):
        properties_dict = {name: prop.to_dict() for name, prop in self.properties.items()}
        methods_dict = {name: method.to_dict() for name, method in self.methods.items()}

        return {
            "name": self.name,
            "id": self.object_id,
            "description": self.description,
            "templates": object.__getattribute__(self, "__templates"),
            "properties": properties_dict,
            "methods": methods_dict,
            "parents": self.parents,
            "permissions": object.__getattribute__(self, "__permissions"),
            "runtime": dict(object.__getattribute__(self, "_runtime")),
        }

    def __str__(self):
        return f"ObjectManager(name='{self.name}', description='{self.description}')"

    def __repr__(self):
        return self.__str__()
