# Автоматизации и Scheduler

Scheduler — системный плагин osysHome, позволяющий выполнять Python-код по расписанию или однократно в заданное время. Это основной инструмент для создания автоматизаций.

---

## Что такое задача (Task)

Каждая **задача** содержит:

- **Имя** — понятное название (например, «Выключить свет в полночь»)
- **Код** — Python-код, который выполнится
- **Расписание** — когда запускать: по Cron-выражению или один раз в указанное время
- **Статус** — активна или приостановлена

---

## Создание задачи

1. Перейдите в **Admin → Scheduler**
2. Нажмите кнопку **«Добавить задачу»**
3. Заполните форму:
   - **Имя** — произвольное название
   - **Код** — Python-код задачи
   - **Cron** — выражение расписания (или оставьте пустым для разового запуска)
   - **Время запуска** — для разового запуска укажите дату и время
4. Нажмите **«Сохранить»**

---

## Синтаксис Cron

Cron-выражения задают повторяющееся расписание:

```
┌─── секунды (0-59)      [необязательно]
│ ┌─── минуты (0-59)
│ │ ┌─── часы (0-23)
│ │ │ ┌─── день месяца (1-31)
│ │ │ │ ┌─── месяц (1-12)
│ │ │ │ │ ┌─── день недели (0-7, 0 и 7 = воскресенье)
│ │ │ │ │ │
* * * * * *
```

### Примеры Cron-выражений

| Выражение | Значение |
|-----------|----------|
| `* * * * *` | Каждую минуту |
| `0 * * * *` | Каждый час (в начале часа) |
| `0 8 * * *` | Каждый день в 8:00 |
| `0 22 * * *` | Каждый день в 22:00 |
| `0 8 * * 1-5` | По будням в 8:00 |
| `0 8,18 * * *` | В 8:00 и 18:00 каждый день |
| `0 0 1 * *` | Первого числа каждого месяца в 00:00 |
| `*/15 * * * *` | Каждые 15 минут |
| `*/30 * * * * *` | Каждые 30 секунд (6 полей — с секундами) |

> Поддержка Cron-формата зависит от установленной версии `croniter`.
> Если используется 6-полевый формат (с секундами), проверьте его в вашем runtime.

---

## Код задачи

В коде задачи доступны предзагруженные функции из модулей:
`app.core.lib.common`, `app.core.lib.constants`,
`app.core.lib.object`, `app.core.lib.cache`, `app.core.lib.sql`,
а также runtime-переменные `params` и `logger`.

### Управление устройствами

```python
# Включить лампу в гостиной
setProperty("LivingRoomLamp.state", True)

# Установить яркость
setProperty("LivingRoomLamp.brightness", 80)

# Выключить все лампы в группе
for lamp in ["LivingRoomLamp", "HallLamp", "KitchenLamp"]:
    setProperty(lamp + ".state", False)
```

### Условная логика

```python
# Включить свет только если дома кто-то есть
presence = getProperty("HomePresence.state")
hour = datetime.now().hour

if presence and 7 <= hour <= 23:
    setProperty("HallLamp.state", True)
else:
    setProperty("HallLamp.state", False)
```

### Уведомления

```python
# Голосовое уведомление через TTS
say("Доброе утро! Сегодня " + str(datetime.now().strftime("%A")))

# Уведомление в Telegram (если настроен плагин TelegramBot)
# setProperty("TelegramBot.message", "Температура в доме: " + str(getProperty("HomeSensor.temperature")))
```

### Работа с несколькими объектами

```python
# Проверить все датчики движения
motion_sensors = ["HallMotion", "KitchenMotion", "LivingRoomMotion"]
any_motion = any(getProperty(s + ".occupancy") for s in motion_sensors)

if not any_motion:
    # Никого нет — выключить всё
    setProperty("MainSwitch.state", False)
    say("Все устройства выключены")
```

---

## Доступные функции в коде задачи

| Функция | Описание |
|---------|----------|
| `getProperty("Obj.prop")` | Получить текущее значение свойства |
| `setProperty("Obj.prop", value)` | Установить значение свойства |
| `callMethod("Obj.method")` | Вызвать метод объекта |
| `say("текст")` | Произнести текст через TTS |
| `playSound("file.mp3")` | Воспроизвести звуковой файл |
| `runCode("код")` | Выполнить строку кода |
| `datetime` | Модуль Python `datetime`, доступный в runtime |
| `logger.info("сообщение")` | Записать в лог задачи |

---

## Примеры автоматизаций

### Утренний сценарий

```python
# Каждый будний день в 7:00: 0 7 * * 1-5
say("Доброе утро! Пора вставать.")
setProperty("BedroomLamp.state", True)
setProperty("BedroomLamp.brightness", 30)  # мягкий свет
setProperty("KettleSocket.state", True)     # включить чайник
```

### Вечерний сценарий

```python
# Каждый день в 22:00: 0 22 * * *
temp = getProperty("OutdoorSensor.temperature")
if temp is not None and temp < 15:
    say("На улице холодно, " + str(round(temp)) + " градусов. Окна закрыты?")
setProperty("LivingRoomLamp.brightness", 20)  # приглушить свет
```

### Ночной режим

```python
# Каждый день в 23:30: 30 23 * * *
# Выключить всё, кроме ночника
devices_off = ["LivingRoomLamp", "KitchenLamp", "HallLamp", "TVSocket"]
for device in devices_off:
    setProperty(device + ".state", False)

# Ночник на минимум
setProperty("BedroomLamp.brightness", 5)
```

### Мониторинг температуры

```python
# Каждые 5 минут: */5 * * * *
temp = getProperty("BoilerSensor.temperature")
if temp is not None and temp < 40:
    say("Внимание! Котёл остывает: " + str(temp) + " градусов")
    setProperty("AlertLight.state", True)
```

### Присутствие и экономия

```python
# Каждые 10 минут: */10 * * * *
presence = getProperty("HomePresence.state")
if not presence:
    # Никого нет дома — минимальный режим
    setProperty("Thermostat.target_temp", 16)
    setProperty("AllLights.state", False)
else:
    # Кто-то есть — комфортный режим
    setProperty("Thermostat.target_temp", 21)
```

---

## Разовые задачи

Если оставить поле **Cron** пустым, задача выполнится **один раз** в указанное время.

Это удобно для:

- Отложенного выполнения («выключить через 2 часа»)
- Напоминаний
- Тестирования кода

---

## Динамическое создание задач из кода

Вы можете создавать задачи программно из методов объектов или других задач:

```python
from app.core.lib.common import setTimeout, clearTimeout

# Создать разовую задачу: выключить лампу через 30 минут
setTimeout(
    name="TurnOffLamp",
    code="setProperty('LivingRoomLamp.state', False)",
    timeout=30 * 60
)

# Отменить задачу
clearTimeout("TurnOffLamp")
```

---

## Мониторинг задач

На странице **Admin → Scheduler** вкладка **Monitoring** показывает:

- Текущее состояние пула потоков
- Статистику выполнения задач
- Задачи, которые выполняются прямо сейчас
- Ошибки последних запусков

Эта информация поможет обнаружить «зависшие» задачи или задачи с ошибками.
