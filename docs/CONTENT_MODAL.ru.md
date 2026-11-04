# Модальные окна контента (showContentModal)

Глобальный UI-хелпер ядра для показа произвольного HTML в Bootstrap-модалке: история свойства, параметры настройки, справка и т.п.

Подключается автоматически через layout (`includes/scripts.html`). В шаблонах объектов, классов и плагинов достаточно вызвать `showContentModal(...)`.

## Файлы

| Файл | Назначение |
|------|------------|
| `app/templates/includes/content_modal.html` | Разметка `#appContentModal` + `ContentModalI18n` |
| `app/static/assets/js/content-modal.js` | API `window.showContentModal` |
| `app/templates/includes/scripts.html` | Подключение include и скрипта |

Связанные диалоги (только текст): `showConfirm` / `showAlert` в `confirm_modal.html` + `confirm-modal.js`. У content modal обычный Bootstrap z-index, у confirm/alert — выше (`1200`), поэтому из контента модалки можно вызвать подтверждение или alert.

## API

```js
showContentModal(options) → Promise  // resolve при закрытии
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|--------------|----------|
| `title` | string | `''` | Заголовок |
| `html` | string | — | Готовый HTML в `modal-body` |
| `url` | string | — | URL HTML-фрагмента (same-origin `fetch`) |
| `size` | `''` \| `'sm'` \| `'lg'` \| `'xl'` | `''` | Класс `modal-*` на dialog |
| `centered` | boolean | `true` | `modal-dialog-centered` |
| `scrollable` | boolean | `true` | `modal-dialog-scrollable` |

Если заданы и `html`, и `url` — используется **`url`**.

При загрузке по `url` в body показывается спиннер («Loading…»). Ошибка fetch выводится в body. При закрытии body, title и size-классы очищаются. Повторный вызов при уже открытой модалке закрывает текущую и открывает новую.

Эндпоинт для `url` должен отдавать **HTML-фрагмент** (без полного layout страницы).

---

## Примеры

### 1. Готовый HTML из `<template>`

```html
<button type="button" class="btn btn-sm btn-outline-secondary"
        onclick="showContentModal({
          title: {{ _('Параметры')|tojson }},
          size: 'lg',
          html: document.getElementById('obj-params-tpl').innerHTML
        })">
  {{ _('Параметры') }}
</button>

<template id="obj-params-tpl">
  <form>
    <div class="mb-3">
      <label class="form-label">{{ _('Timeout') }}</label>
      <input type="number" class="form-control" name="timeout" value="30">
    </div>
  </form>
</template>
```

### 2. Контент с сервера (`url`)

```html
<button type="button" class="btn btn-sm btn-outline-secondary"
        onclick="showContentModal({
          title: {{ _('История')|tojson }},
          size: 'xl',
          url: {{ url_for('Objects.property_history', id=property.id)|tojson }}
        })">
  {{ _('История') }}
</button>
```

Фрагмент на сервере:

```html
{# например property_history_fragment.html #}
<table class="table table-sm">
  <thead>
    <tr><th>{{ _('Time') }}</th><th>{{ _('Value') }}</th></tr>
  </thead>
  <tbody>
    {% for row in history %}
    <tr>
      <td>{{ row.changed }}</td>
      <td>{{ row.value }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

### 3. Из JS без `onclick` в разметке

```html
<button type="button" class="btn btn-sm btn-outline-secondary" id="btn-history">
  {{ _('История') }}
</button>

<script>
  document.getElementById('btn-history').addEventListener('click', function () {
    showContentModal({
      title: {{ _('История')|tojson }},
      size: 'xl',
      url: '/Objects/property/{{ property.id }}/history'
    }).then(function () {
      // модалка закрыта
    });
  });
</script>
```

### 4. Шаблон объекта (Jinja2, extends класса)

Пример для объекта класса `Motion`: кнопка в `object_ext` рядом с унаследованным контентом.

```jinja2
{% extends "Motion" %}
{% block object_ext %}
{{ super() }}
<button type="button" class="btn btn-sm btn-outline-secondary ms-1"
        title="Инфо"
        onclick="showContentModal({
          title: '{{ object.name }}',
          size: 'lg',
          html: document.getElementById('{{ object.name }}_content_modal_demo').innerHTML
        })">
  <i class="fas fa-info-circle"></i>
</button>
<template id="{{ object.name }}_content_modal_demo">
  <div class="mb-2"><strong>Объект:</strong> {{ object.name }}</div>
  <div class="mb-2"><strong>status:</strong> {{ object.status }}</div>
  <div><strong>updated:</strong> {{ object.updated }}</div>
</template>
{% endblock %}
```

Шаблон объекта задаётся в Objects (поле Template) или через MCP: `osys_update_object` с полем `template`.

---

## Замечания

- Контент вставляется через `innerHTML` — доверяйте только своему HTML / same-origin ответам.
- Разметку `#appContentModal` в шаблоне плагина дублировать не нужно.
- Для простых текстовых сообщений используйте `showAlert` / `showConfirm`, не content modal.
