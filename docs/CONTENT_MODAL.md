# Content modals (showContentModal)

Core UI helper for showing arbitrary HTML in a Bootstrap modal: property history, settings forms, help text, etc.

Loaded automatically via the layout (`includes/scripts.html`). In object, class, and plugin templates you only call `showContentModal(...)`.

## Files

| File | Purpose |
|------|---------|
| `app/templates/includes/content_modal.html` | Markup `#appContentModal` + `ContentModalI18n` |
| `app/static/assets/js/content-modal.js` | `window.showContentModal` API |
| `app/templates/includes/scripts.html` | Include + script wiring |

Related text-only dialogs: `showConfirm` / `showAlert` in `confirm_modal.html` + `confirm-modal.js`. Content modal uses the default Bootstrap z-index; confirm/alert sit higher (`1200`), so you can open confirm/alert from inside content.

## API

```js
showContentModal(options) → Promise  // resolves when closed
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | `''` | Modal title |
| `html` | string | — | HTML injected into `modal-body` |
| `url` | string | — | URL of an HTML fragment (same-origin `fetch`) |
| `size` | `''` \| `'sm'` \| `'lg'` \| `'xl'` | `''` | `modal-*` class on the dialog |
| `centered` | boolean | `true` | `modal-dialog-centered` |
| `scrollable` | boolean | `true` | `modal-dialog-scrollable` |

If both `html` and `url` are set, **`url` wins**.

While fetching `url`, the body shows a loading spinner. Fetch errors are shown in the body. On close, body, title, and size classes are cleared. Calling again while open closes the current modal and opens the new one.

The `url` endpoint must return an **HTML fragment** (not a full page layout).

---

## Examples

### 1. Inline HTML from a `<template>`

```html
<button type="button" class="btn btn-sm btn-outline-secondary"
        onclick="showContentModal({
          title: {{ _('Settings')|tojson }},
          size: 'lg',
          html: document.getElementById('obj-params-tpl').innerHTML
        })">
  {{ _('Settings') }}
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

### 2. Server fragment (`url`)

```html
<button type="button" class="btn btn-sm btn-outline-secondary"
        onclick="showContentModal({
          title: {{ _('History')|tojson }},
          size: 'xl',
          url: {{ url_for('Objects.property_history', id=property.id)|tojson }}
        })">
  {{ _('History') }}
</button>
```

Server fragment:

```html
{# e.g. property_history_fragment.html #}
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

### 3. From JS without inline `onclick`

```html
<button type="button" class="btn btn-sm btn-outline-secondary" id="btn-history">
  {{ _('History') }}
</button>

<script>
  document.getElementById('btn-history').addEventListener('click', function () {
    showContentModal({
      title: {{ _('History')|tojson }},
      size: 'xl',
      url: '/Objects/property/{{ property.id }}/history'
    }).then(function () {
      // modal closed
    });
  });
</script>
```

### 4. Object template (Jinja2, extends class)

Example for a `Motion` object: button in `object_ext` next to inherited content.

```jinja2
{% extends "Motion" %}
{% block object_ext %}
{{ super() }}
<button type="button" class="btn btn-sm btn-outline-secondary ms-1"
        title="Info"
        onclick="showContentModal({
          title: '{{ object.name }}',
          size: 'lg',
          html: document.getElementById('{{ object.name }}_content_modal_demo').innerHTML
        })">
  <i class="fas fa-info-circle"></i>
</button>
<template id="{{ object.name }}_content_modal_demo">
  <div class="mb-2"><strong>Object:</strong> {{ object.name }}</div>
  <div class="mb-2"><strong>status:</strong> {{ object.status }}</div>
  <div><strong>updated:</strong> {{ object.updated }}</div>
</template>
{% endblock %}
```

Set the object template in Objects (Template field) or via MCP `osys_update_object` with `template`.

---

## Notes

- Content is injected via `innerHTML` — only trust your own HTML / same-origin responses.
- Do not duplicate `#appContentModal` markup in plugin templates.
- For plain text prompts use `showAlert` / `showConfirm`, not the content modal.
