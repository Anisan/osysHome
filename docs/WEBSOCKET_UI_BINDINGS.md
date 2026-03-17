## WebSocket UI bindings (EN)

This document describes lightweight HTML bindings that connect WebSocket updates to **UI changes** in templates:

- property updates (`changeProperty`),
- method updates (`executedMethod`),
- object HTML updates (`changeObject`),
- additional declarative bindings (`data-prop-*`).

Implementation lives in `app/templates/includes/websockets.html`:

- `subscribe()` automatically subscribes to properties used in bindings.
- `socket.on('changeProperty', ...)` applies property bindings on updates.
- `socket.on('executedMethod', ...)` applies method bindings on updates.
- `socket.on('changeObject', ...)` morphs HTML inside `id="obj:..."`.

---

### 1. How it works

1. You add elements that follow one of the binding conventions below (`id="prop:..."`, `data-prop-*`, `id="obj:..."`, etc.).
2. On connect, the browser calls `subscribe()`.
3. `subscribe()` gathers property names from:
   - id-based property markers: `id="prop:<PropertyName>"`
   - declarative property bindings:
     - `data-prop-display`, `data-prop-text`, `data-prop-value`, `data-prop-checked`, `data-prop-attr-*`
4. `subscribe()` gathers object names from:
   - object containers: `id="obj:<ObjectName>"`
4. When the backend emits `changeProperty` for a subscribed property, the UI updates.
5. When the backend emits `executedMethod` for a method, the method UI updates (if such elements exist).
6. When the backend emits `changeObject`, the HTML inside `id="obj:<ObjectName>"` is updated.

Notes:

- If you want to avoid “flash of visible content” before the first WebSocket value arrives, set an explicit initial state in HTML/CSS (for example `style="display:none"`).

---

### 2. Supported bindings (property → UI)

There are two styles:

- **id-based**: `id="prop:..."`, `id="prop_changed:..."`, `id="prop_source:..."`
- **declarative**: `data-prop-*` (recommended for most new UI)

#### 2.1. Property value (id-based): `id="prop:<PropertyName>"`

The global handler updates `textContent` on elements with this exact id.

```html
<span id="prop:SystemVar.NeedRestart" style="display:none"></span>
```

#### 2.2. Property changed timestamp (id-based): `id="prop_changed:<PropertyName>"`

```html
<span id="prop_changed:My.Object.Temp"></span>
```

#### 2.3. Property source (id-based): `id="prop_source:<PropertyName>"`

```html
<span id="prop_source:My.Object.Temp"></span>
```

#### 2.4. Visibility (declarative): `data-prop-display` (boolean → `style.display`)

Show/hide an element based on a boolean-ish property.

```html
<div data-prop-display="SystemVar.NeedRestart" style="display:none;">
  Need restart
</div>
```

Optional overrides (defaults: `block`/`none`):

```html
<span data-prop-display="My.Flag"
      data-prop-display-true="inline-block"
      data-prop-display-false="none"
      style="display:none;">
  ...
</span>
```

#### 2.5. Text content (declarative): `data-prop-text` (`textContent`)

```html
<span data-prop-text="Sensors.TempLiving"></span>
```

Objects are stringified as JSON.

#### 2.6. Form value (declarative): `data-prop-value` (`value`)

For `input`, `textarea`, `select` (and any node exposing `.value`).

```html
<input type="text" data-prop-value="User.ProfileName" />
```

#### 2.7. Checked state (declarative): `data-prop-checked` (`checked`)

For checkboxes/toggles.

```html
<input type="checkbox" data-prop-checked="My.Enabled" />
```

#### 2.8. Any attribute (declarative): `data-prop-attr-<attrName>` (`setAttribute`)

Bind a property to any attribute by using `data-prop-attr-<attrName>`.

```html
<a data-prop-attr-href="My.Link">Open</a>
<img data-prop-attr-src="My.ImageUrl" />
<button data-prop-attr-title="My.Tooltip">...</button>
<div data-prop-attr-aria-label="My.AriaLabel"></div>
```

---

### 3. Supported bindings (method → UI)

When the backend emits `executedMethod`, the global handler updates elements by id.

#### 3.1. Method source: `id="method_source:<MethodName>"`

```html
<span id="method_source:My.Object.MyMethod"></span>
```

#### 3.2. Method executed flag/time: `id="method_executed:<MethodName>"`

```html
<span id="method_executed:My.Object.MyMethod"></span>
```

#### 3.3. Method params: `id="method_exec_params:<MethodName>"`

```html
<span id="method_exec_params:My.Object.MyMethod"></span>
```

#### 3.4. Method result: `id="method_exec_result:<MethodName>"`

```html
<span id="method_exec_result:My.Object.MyMethod"></span>
```

#### 3.5. Method execution time: `id="method_exec_time:<MethodName>"`

```html
<span id="method_exec_time:My.Object.MyMethod"></span>
```

---

### 4. Supported bindings (object HTML → UI)

#### 4.1. Object container: `id="obj:<ObjectName>"`

If you have an element like:

```html
<div id="obj:LivingRoom">
  <!-- server-rendered HTML -->
</div>
```

Then on WebSocket `changeObject` updates, the client will update the HTML **inside** that wrapper in-place.

#### 4.2. Preserve visibility across morphing: `data-preserve-display="true"`

During object morphing, if an element has `data-preserve-display="true"`, the current `style.display` is carried over to the new DOM.

```html
<div data-preserve-display="true" style="display:none">...</div>
```

---

### 5. Legacy compatibility summary

Existing id-based patterns still work and participate in auto-subscribe:

- `id="prop:<PropertyName>"`
- `id="prop_changed:<PropertyName>"`
- `id="prop_source:<PropertyName>"`
- `id="obj:<ObjectName>"`

Existing pattern still works:

```html
<span id="prop:SystemVar.NeedRestart" style="display:none"></span>
```

It is still used to:

- auto-subscribe to a property,
- store the last seen value as text in the DOM.

---

## WebSocket биндинги UI (RU)

Этот документ описывает простые HTML-привязки, которые связывают события WebSocket с **обновлением UI** в шаблонах:

- обновления property (`changeProperty`),
- обновления методов (`executedMethod`),
- обновления HTML объекта (`changeObject`),
- декларативные биндинги (`data-prop-*`).

Реализация находится в `app/templates/includes/websockets.html`:

- `subscribe()` автоматически подписывается на свойства, которые используются в биндингах.
- `socket.on('changeProperty', ...)` применяет биндинги при обновлениях.

---

### 1. Как это работает

1. В шаблоне вы добавляете элементы, которые следуют одному из соглашений ниже (`id="prop:..."`, `data-prop-*`, `id="obj:..."` и т.п.).
2. При подключении браузер вызывает `subscribe()`.
3. `subscribe()` собирает список свойств из:
   - id-маркеров: `id="prop:<ИмяСвойства>"`
   - декларативных биндингов:
     - `data-prop-display`, `data-prop-text`, `data-prop-value`, `data-prop-checked`, `data-prop-attr-*`
4. `subscribe()` собирает список объектов из:
   - контейнеров: `id="obj:<ИмяОбъекта>"`
4. Когда бэкенд отправляет `changeProperty` по подписанному свойству, UI автоматически обновляется.
5. Когда бэкенд отправляет `executedMethod`, UI методов обновляется (если на странице есть соответствующие элементы).
6. Когда бэкенд отправляет `changeObject`, обновляется HTML внутри `id="obj:<ИмяОбъекта>"`.

Примечание:

- Чтобы не было “моргания” (элемент виден до прихода первого значения), задавайте начальное состояние прямо в HTML/CSS (например `style="display:none"`).

---

### 2. Доступные биндинги (property → UI)

Есть два стиля:

- **id-based**: `id="prop:..."`, `id="prop_changed:..."`, `id="prop_source:..."`
- **declarative**: `data-prop-*` (рекомендуется для новой UI-разметки)

#### 2.1. Значение property (id-based): `id="prop:<ИмяСвойства>"`

Глобальный обработчик обновляет `textContent` элемента с этим id.

```html
<span id="prop:SystemVar.NeedRestart" style="display:none"></span>
```

#### 2.2. Время изменения (id-based): `id="prop_changed:<ИмяСвойства>"`

```html
<span id="prop_changed:My.Object.Temp"></span>
```

#### 2.3. Источник значения (id-based): `id="prop_source:<ИмяСвойства>"`

```html
<span id="prop_source:My.Object.Temp"></span>
```

#### 2.4. Видимость (declarative): `data-prop-display` (boolean → `style.display`)

```html
<div data-prop-display="SystemVar.NeedRestart" style="display:none;">
  Требуется перезапуск
</div>
```

Переопределение `display` (по умолчанию: `block`/`none`):

```html
<span data-prop-display="My.Flag"
      data-prop-display-true="inline-block"
      data-prop-display-false="none"
      style="display:none;">
  ...
</span>
```

#### 2.5. Текст (declarative): `data-prop-text` (`textContent`)

```html
<span data-prop-text="Sensors.TempLiving"></span>
```

Если значение — объект, он будет сериализован в JSON.

#### 2.6. Значение поля (declarative): `data-prop-value` (`value`)

Для `input`, `textarea`, `select` (и любых элементов, где есть `.value`).

```html
<input type="text" data-prop-value="User.ProfileName" />
```

#### 2.7. Чекбокс/переключатель (declarative): `data-prop-checked` (`checked`)

```html
<input type="checkbox" data-prop-checked="My.Enabled" />
```

#### 2.8. Любой атрибут (declarative): `data-prop-attr-<имя_атрибута>` (`setAttribute`)

Привязка свойства к любому атрибуту через `data-prop-attr-<имя_атрибута>`.

```html
<a data-prop-attr-href="My.Link">Открыть</a>
<img data-prop-attr-src="My.ImageUrl" />
<button data-prop-attr-title="My.Tooltip">...</button>
<div data-prop-attr-aria-label="My.AriaLabel"></div>
```

---

---

### 3. Доступные биндинги (method → UI)

Когда бэкенд отправляет `executedMethod`, глобальный обработчик обновляет элементы по id.

#### 3.1. Источник метода: `id="method_source:<ИмяМетода>"`

```html
<span id="method_source:My.Object.MyMethod"></span>
```

#### 3.2. Метка/время выполнения: `id="method_executed:<ИмяМетода>"`

```html
<span id="method_executed:My.Object.MyMethod"></span>
```

#### 3.3. Параметры запуска: `id="method_exec_params:<ИмяМетода>"`

```html
<span id="method_exec_params:My.Object.MyMethod"></span>
```

#### 3.4. Результат: `id="method_exec_result:<ИмяМетода>"`

```html
<span id="method_exec_result:My.Object.MyMethod"></span>
```

#### 3.5. Время выполнения (ms): `id="method_exec_time:<ИмяМетода>"`

```html
<span id="method_exec_time:My.Object.MyMethod"></span>
```

---

### 4. Доступные биндинги (object HTML → UI)

#### 4.1. Контейнер объекта: `id="obj:<ИмяОбъекта>"`

Если на странице есть:

```html
<div id="obj:LivingRoom">
  <!-- server-rendered HTML -->
</div>
```

то при WebSocket событии `changeObject` клиент обновит HTML **внутри** этого контейнера (wrapper сохраняется).

#### 4.2. Сохранение видимости при morphdom: `data-preserve-display="true"`

Во время морфинга объекта, если элемент имеет `data-preserve-display="true"`, его текущий `style.display` будет перенесён в новый DOM.

```html
<div data-preserve-display="true" style="display:none">...</div>
```

---

### 5. Резюме про “старые” id-паттерны

Старые id-паттерны остаются рабочими и участвуют в авто-подписке:

- `id="prop:<ИмяСвойства>"`
- `id="prop_changed:<ИмяСвойства>"`
- `id="prop_source:<ИмяСвойства>"`
- `id="obj:<ИмяОбъекта>"`

### 6. Обратная совместимость: `id="prop:..."`

Старый способ остаётся рабочим:

```html
<span id="prop:SystemVar.NeedRestart" style="display:none"></span>
```

Он по-прежнему используется чтобы:

- автоматически подписаться на property,
- хранить последнее полученное значение в DOM (текстом).

