# Связывание свойств с плагинами (Binding)

Связывание — ключевой механизм osysHome, соединяющий **виртуальный объект** в базе данных с **реальным физическим устройством**, которым управляет плагин.

> **Важно:** связи **всегда настраиваются пользователем вручную** в интерфейсе плагина. Система никогда не устанавливает связи автоматически без участия пользователя.

---

## Зачем нужно связывание

В osysHome объект `LivingRoomLamp` — это запись в базе данных. Физическая лампа управляется плагином (MQTT, Tuya, z2m и т.д.). Связывание создаёт «мост» между ними:

- Когда **лампа сообщает о своём состоянии** → плагин принимает событие от устройства и обновляет свойство объекта в системе
- Когда **система меняет значение** (`setProperty("LivingRoomLamp.state", True)` из автоматизации) → ObjectManager уведомляет плагин → плагин отправляет команду физическому устройству

```
Физическое устройство
        ↕  (MQTT / Tuya / Zigbee / ESPHome / ...)
    Плагин
        ↕  (связь, настроенная пользователем)
 Объект.Свойство  ←→  ObjectManager  ←→  Автоматизации / API / UI
```

---

## Двухуровневая архитектура связи

Каждый плагин хранит конфигурацию связей в **собственной таблице БД**. Ядро системы хранит эти связи в поле `Value.linked`. Оба уровня обновляются одновременно, когда пользователь сохраняет настройки в UI плагина.

### Уровень 1 — таблица плагина

Каждый плагин ведёт свою таблицу с записями о физических сущностях (топики MQTT, устройства Zigbee, DPS-коды Tuya и т.д.). Каждая запись содержит поля:

| Поле | Описание |
|------|----------|
| `linked_object` | Имя объекта в osysHome (например, `LivingRoomLamp`) |
| `linked_property` | Имя свойства объекта (например, `state`) |
| … | Прочие поля плагина (топик, device ID, code и т.д.) |

Именно эта таблица — источник истины для конфигурации плагина.

### Уровень 2 — `Value.linked` в ядре

Поле `linked` записи `Value` — это строка с именами плагинов через запятую. ObjectManager использует её, чтобы знать, кого уведомить при изменении значения.

```
Value.linked = "Mqtt"        # при изменении свойства → вызвать MqttPlugin.changeLinkedProperty(...)
Value.linked = "Mqtt,Tuya"   # уведомить два плагина
Value.linked = ""            # свойство ни с чем не связано
```

### Синхронизация уровней

Когда пользователь сохраняет настройки в UI плагина, плагин сам вызывает `setLinkToObject`:

```python
# Внутри обработчика формы плагина — вызывается при сохранении пользователем
from app.core.lib.object import setLinkToObject, removeLinkFromObject

# Снять старую связь (если была)
removeLinkFromObject(old_object, old_property, "Mqtt")

# Установить новую связь
setLinkToObject(new_object, new_property, "Mqtt")
```

---

## Как настроить связь

### Пример: MQTT

1. Перейдите в **Admin → Mqtt**
2. Создайте или откройте запись топика
3. В поле **Linked object** введите имя объекта (например, `LivingRoomLamp`)
4. В поле **Linked property** введите имя свойства (например, `state`)
5. Нажмите **Сохранить**

После сохранения форма автоматически:

- Обновит `Topic.linked_object` и `Topic.linked_property` в таблице MQTT
- Вызовет `setLinkToObject("LivingRoomLamp", "state", "Mqtt")`
- В `Value.linked` появится `"Mqtt"`

### Пример: Zigbee2MQTT (z2m)

1. Перейдите в **Admin → z2m**
2. Найдите устройство и нужное свойство (exposes)
3. В строке свойства заполните **Linked object** и **Linked property**
4. Нажмите **Сохранить** — плагин вызовет `setLinkToObject`

### Пример: Tuya

1. Перейдите в **Admin → Tuya** → нужное устройство
2. В таблице DPS-кодов для каждого кода укажите **Linked object** и **Linked property**
3. Нажмите **Save links** — плагин вызовет `setLinkToObject` для каждого кода

---

## Как работает связь при изменении свойства

### Система → Физическое устройство

```
Автоматизация: setProperty("LivingRoomLamp.state", True)
        ↓
ObjectManager:
  1. Сохраняет значение в БД
  2. Вызывает метод объекта (если привязан к свойству)
  3. Читает Value.linked  →  ["Mqtt"]
  4. Для каждого плагина (кроме source):
       MqttPlugin.changeLinkedProperty("LivingRoomLamp", "state", True)
        ↓
Mqtt находит в своей таблице: Topic где linked_object="LivingRoomLamp", linked_property="state"
        ↓
Mqtt публикует значение в топик физической лампы
        ↓
Лампа включается физически
```

### Физическое устройство → Система

```
Лампа физически изменила состояние → отправила событие в MQTT broker
        ↓
Плагин Mqtt получает сообщение
        ↓
setProperty("LivingRoomLamp.state", True, source="Mqtt")
        ↓
ObjectManager:
  • Сохраняет значение
  • Value.linked = "Mqtt", но source = "Mqtt" → пропустить (защита от петли)
  • proxy-плагины: уведомить
  • WebSocket: обновить Dashboard в браузере
```

### Защита от петли

Параметр `source` передаётся при каждом вызове `setProperty`. Если источник изменения совпадает с именем плагина в `linked` — обратный вызов пропускается:

```python
# Физическое устройство → Mqtt → система
setProperty("LivingRoomLamp.state", True, source="Mqtt")
# ObjectManager: Mqtt есть в linked, но source="Mqtt" → skip → нет петли
```

---

## Метод `changeLinkedProperty`

Каждый плагин, управляющий физическими устройствами, реализует этот метод:

```python
def changeLinkedProperty(self, obj: str, prop: str, val):
    """
    Вызывается ObjectManager'ом, когда связанное свойство изменилось.
    obj  — имя объекта (например, "LivingRoomLamp")
    prop — имя свойства (например, "state")
    val  — новое значение
    """
    # Найти соответствующую запись в таблице плагина
    records = session.query(Topic).filter(
        Topic.linked_object == obj,
        Topic.linked_property == prop
    ).all()

    if not records:
        # Запись была удалена пользователем — снять связь
        removeLinkFromObject(obj, prop, self.name)
        return

    for rec in records:
        if not rec.readonly:
            self.mqttPublish(rec.path_write or rec.path, val)
```

Плагин ищет запись в **своей** таблице по паре `(linked_object, linked_property)`. Если запись не найдена (пользователь удалил топик) — связь снимается автоматически.

---

## Полный пример: лампа через MQTT

**Шаг 1. Пользователь настраивает топик в Admin → Mqtt:**

```
Title:          Лампа в гостиной
Path:           home/living_room/lamp/state
Path write:     home/living_room/lamp/set
Linked object:  LivingRoomLamp
Linked property: state
```

После сохранения: `Value["LivingRoomLamp.state"].linked = "Mqtt"`

**Шаг 2. Автоматизация включает лампу:**

```
setProperty("LivingRoomLamp.state", True)
→ Mqtt.changeLinkedProperty("LivingRoomLamp", "state", True)
→ publish("home/living_room/lamp/set", True)
→ Лампа включается
```

**Шаг 3. Лампа подтверждает состояние:**

```
Лампа публикует True в "home/living_room/lamp/state"
→ Mqtt: setProperty("LivingRoomLamp.state", True, source="Mqtt")
→ ObjectManager: пропустить Mqtt (source), уведомить proxy, обновить UI
```
