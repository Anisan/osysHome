import json
import os
import sys
import re
import subprocess
import tempfile
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple
from app.logging_config import getLogger
from app.core.lib.execute import MODULE_NAMES
from app.core.lib.object import getObject
from app.core.main.ObjectsStorage import objects_storage

logger = getLogger("lsp")


class PylspClient:
    """
    Минимальный LSP-клиент для pylsp по stdio.
    Держим один процесс на всё приложение, синхронизируем вызовы локом.
    """

    def _is_identifier(self, name: str) -> bool:
        return isinstance(name, str) and name.isidentifier()

    def _word_at(self, code: str, line: int, col: int) -> str:
        try:
            lines = code.splitlines()
            if line - 1 < 0 or line - 1 >= len(lines):
                return ""
            text = lines[line - 1]
            pos = max(0, min(len(text), col))
            left = pos
            while left > 0 and (text[left - 1].isalnum() or text[left - 1] == "_"):
                left -= 1
            right = pos
            while right < len(text) and (text[right].isalnum() or text[right] == "_"):
                right += 1
            return text[left:right]
        except Exception:
            return ""

    def _prefix_at(self, code: str, line: int, col: int) -> str:
        try:
            lines = code.splitlines()
            if line - 1 < 0 or line - 1 >= len(lines):
                return ""
            text = lines[line - 1]
            pos = max(0, min(len(text), col))
            left = pos
            while left > 0 and (text[left - 1].isalnum() or text[left - 1] == "_"):
                left -= 1
            return text[left:pos]
        except Exception:
            return ""

    def _is_self_context(self, code: str, line: int, col: int) -> bool:
        try:
            lines = code.splitlines()
            if line - 1 < 0 or line - 1 >= len(lines):
                return False
            before = lines[line - 1][: max(0, col)]
            return bool(re.search(r"self\s*\.[A-Za-z0-9_]*$", before))
        except Exception:
            return False

    def _object_member_context(self, code: str, line: int, col: int) -> Optional[Tuple[str, str]]:
        """
        Возвращает (object_name, member_name) если курсор находится на члене объекта (object.member).
        """
        try:
            lines = code.splitlines()
            if line - 1 < 0 or line - 1 >= len(lines):
                return None
            cursor_line = lines[line - 1]
            cursor_pos = max(0, min(len(cursor_line), col))

            # Проверяем, находится ли курсор на идентификаторе
            if cursor_pos <= 0 or not (cursor_line[cursor_pos - 1].isalnum() or cursor_line[cursor_pos - 1] == "_"):
                return None

            # Ищем начало текущего слова (идентификатора)
            word_start = cursor_pos - 1
            while word_start > 0 and (cursor_line[word_start - 1].isalnum() or cursor_line[word_start - 1] == "_"):
                word_start -= 1

            # Ищем точку перед этим словом
            dot_pos = word_start - 1
            while dot_pos >= 0 and cursor_line[dot_pos] != ".":
                dot_pos -= 1

            if dot_pos < 0:
                return None

            # Ищем начало имени объекта (перед точкой)
            obj_start = dot_pos - 1
            while obj_start >= 0 and (cursor_line[obj_start].isalnum() or cursor_line[obj_start] == "_"):
                obj_start -= 1
            obj_start += 1

            if obj_start >= dot_pos:
                return None

            obj_name = cursor_line[obj_start:dot_pos]
            # Полное имя члена от точки до конца слова
            word_end = word_start
            while word_end < len(cursor_line) and (cursor_line[word_end].isalnum() or cursor_line[word_end] == "_"):
                word_end += 1
            member_name = cursor_line[dot_pos + 1:word_end]

            if not obj_name or not member_name or not obj_name.isidentifier() or not member_name.isidentifier():
                return None

            return obj_name, member_name
        except Exception:
            return None

    def _getproperty_context(
        self,
        code: str,
        line: int,
        col: int,
        fn_names: Tuple[str, ...] = (
            "getProperty",
            "setProperty",
            "updateProperty",
            "setPropertyThread",
            "setPropertyTimeout",
            "updatePropertyThread",
            "updatePropertyTimeout",
        ),
    ) -> Optional[Tuple[str, str, bool, Optional[str]]]:
        """
        Возвращает (prefix, quote, in_string, obj_name) если курсор внутри первого аргумента
        getProperty/setProperty/updateProperty и их вариантов. obj_name установлен, если вызов
        идёт как <object>.getProperty(...).
        Использует кэширование для оптимизации производительности.
        """
        # Создаем ключ для кэширования
        cache_key = f"getproperty:{hash(code)}:{line}:{col}"

        # Проверяем кэш
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        try:
            lines = code.splitlines()
            if line < 1 or line > len(lines):
                result = None
            else:
                cursor_index = sum(len(line_text) + 1 for line_text in lines[: line - 1]) + col
                before = code[:cursor_index]
                names_alt = "|".join(map(re.escape, fn_names))
                pattern = re.compile(rf"([A-Za-z_][A-Za-z0-9_]*\.)?({names_alt})\(")
                last_match = None
                for m in pattern.finditer(before):
                    last_match = m
                if not last_match:
                    result = None
                else:
                    obj_name = None
                    if last_match.group(1):
                        obj_name = last_match.group(1).rstrip(".")
                    arg_part = before[last_match.end():]
                    if ")" in arg_part or "," in arg_part:
                        result = None
                    else:
                        last_single = arg_part.rfind("'")
                        last_double = arg_part.rfind('"')
                        last_quote_pos = max(last_single, last_double)
                        in_string = last_quote_pos != -1
                        quote = arg_part[last_quote_pos] if in_string else '"'
                        prefix = arg_part[last_quote_pos + 1:] if in_string else arg_part.strip()
                        result = prefix, quote, in_string, obj_name

            # Кэшируем результат
            if len(self._context_cache) > 20:
                oldest_key = next(iter(self._context_cache))
                del self._context_cache[oldest_key]
            self._context_cache[cache_key] = result
            return result
        except Exception:
            result = None
            self._context_cache[cache_key] = result
            return result

    def _call_arg_at_cursor(
        self,
        code: str,
        line: int,
        col: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Универсальный парсер первого аргумента для вызовов вида
        getProperty/setProperty/callMethod и их вариантов. Поддерживает obj.member
        и вариант без точки: "member" => объект self. member_key определяется
        автоматически по имени функции в текущей строке (callMethod* => method,
        иначе property).
        """
        try:
            lines = code.splitlines()
            if line < 1 or line > len(lines):
                return None
            line_text = lines[line - 1]
            base_index = sum(len(text) + 1 for text in lines[: line - 1])
            cursor_index = base_index + col
            property_fn_names: Tuple[str, ...] = (
                "getProperty",
                "setProperty",
                "updateProperty",
                "setPropertyThread",
                "setPropertyTimeout",
                "updatePropertyThread",
                "updatePropertyTimeout",
            )
            method_fn_names: Tuple[str, ...] = (
                "callMethod",
                "callMethodThread",
                "callMethodTimeout",
            )
            names_alt = "|".join(map(re.escape, property_fn_names + method_fn_names))
            pattern = re.compile(
                rf"({names_alt})\(\s*([\"'])([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?\2"
            )
            for m in pattern.finditer(line_text):
                fn_name = m.group(1) or ""
                obj_name = m.group(3)
                member_name = m.group(4)
                resolved_member_key = "method" if "callmethod" in fn_name.lower() else "property"
                if member_name:
                    obj_span = (base_index + m.start(3), base_index + m.end(3))
                    member_span = (base_index + m.start(4), base_index + m.end(4))
                else:
                    member_name = obj_name
                    obj_name = "self"
                    obj_span = None
                    member_span = (base_index + m.start(3), base_index + m.end(3))
                in_obj = obj_span is not None and obj_span[0] <= cursor_index <= obj_span[1]
                in_member = member_span is not None and member_span[0] <= cursor_index <= member_span[1]
                if not (in_obj or in_member):
                    continue
                return {
                    "object": obj_name,
                    resolved_member_key: member_name,
                    "obj_span": obj_span,
                    f"{resolved_member_key}_span": member_span,
                    "cursor_index": cursor_index,
                }
            return None
        except Exception:
            return None

    def _callmethod_context(
        self,
        code: str,
        line: int,
        col: int,
        fn_names: Tuple[str, ...] = (
            "callMethod",
            "callMethodThread",
            "callMethodTimeout",
        ),
    ) -> Optional[Tuple[str, str, bool, Optional[str]]]:
        """
        Возвращает (prefix, quote, in_string, obj_name) если курсор внутри первого аргумента
        callMethod и его вариантов. obj_name установлен, если вызов идёт как <object>.callMethod(...).
        Использует кэширование для оптимизации производительности.
        """
        # Создаем ключ для кэширования
        cache_key = f"callmethod:{hash(code)}:{line}:{col}"

        # Проверяем кэш
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        try:
            lines = code.splitlines()
            if line < 1 or line > len(lines):
                result = None
            else:
                cursor_index = sum(len(line_text) + 1 for line_text in lines[: line - 1]) + col
                before = code[:cursor_index]
                names_alt = "|".join(map(re.escape, fn_names))
                pattern = re.compile(rf"([A-Za-z_][A-Za-z0-9_]*\.)?({names_alt})\(")
                last_match = None
                for m in pattern.finditer(before):
                    last_match = m
                if not last_match:
                    result = None
                else:
                    obj_name = None
                    if last_match.group(1):
                        obj_name = last_match.group(1).rstrip(".")
                    arg_part = before[last_match.end():]
                    if ")" in arg_part or "," in arg_part:
                        result = None
                    else:
                        last_single = arg_part.rfind("'")
                        last_double = arg_part.rfind('"')
                        last_quote_pos = max(last_single, last_double)
                        in_string = last_quote_pos != -1
                        quote = arg_part[last_quote_pos] if in_string else '"'
                        prefix = arg_part[last_quote_pos + 1:] if in_string else arg_part.strip()
                        result = prefix, quote, in_string, obj_name

            # Кэшируем результат
            if len(self._context_cache) > 20:
                oldest_key = next(iter(self._context_cache))
                del self._context_cache[oldest_key]
            self._context_cache[cache_key] = result
            return result
        except Exception:
            result = None
            self._context_cache[cache_key] = result
            return result

    def _prepare_lsp_code(self, user_code: str, object_name: Optional[str] = None) -> tuple[str, int]:
        """
        Добавляет в пользовательский код пролог с импортами и подсказкой типа self.
        Возвращает готовый текст и смещение строк пролога.
        Использует кэширование для оптимизации производительности.
        """
        cache_key = (user_code, object_name)

        # Проверяем кэш
        if cache_key in self._prepared_code_cache:
            return self._prepared_code_cache[cache_key]

        # Создаем пролог
        prelude_lines = [f"from {mod} import *" for mod in MODULE_NAMES]
        if object_name:
            prelude_lines.append("from app.core.main.ObjectManager import ObjectManager")
            prelude_lines.append("self: ObjectManager = None  # type: ignore")
        prelude_lines.append("")
        prelude_line_count = len(prelude_lines)
        full_code = "\n".join(prelude_lines + [user_code or ""])

        # Кэшируем результат (ограничиваем размер кэша)
        if len(self._prepared_code_cache) > 100:
            # Удаляем самый старый элемент (простая LRU стратегия)
            oldest_key = next(iter(self._prepared_code_cache))
            del self._prepared_code_cache[oldest_key]

        self._prepared_code_cache[cache_key] = (full_code, prelude_line_count)
        return full_code, prelude_line_count

    def _shift_range(self, rng: Optional[Dict[str, Any]], line_offset: int) -> Optional[Dict[str, Any]]:
        if not rng:
            return None
        start = rng.get("start", {})
        end = rng.get("end", start)
        return {
            "start": {
                "line": max(0, (start.get("line") or 0) - line_offset),
                "character": start.get("character", 0),
            },
            "end": {
                "line": max(0, (end.get("line") or 0) - line_offset),
                "character": end.get("character", 0),
            },
        }

    def _filter_diagnostics(self, diags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ignore_codes = {"F405", "F403", "F401", "E402"}
        skip_phrases = [
            "unable to detect undefined names",
            "imported but unused",
        ]
        filtered = []
        for d in diags or []:
            code = str(d.get("code", "")).strip()
            message = (d.get("message") or d.get("msg") or "").lower()
            if code in ignore_codes:
                continue
            if any(phrase in message for phrase in skip_phrases):
                continue
            if "may be undefined, or defined from star imports" in message:
                continue
            filtered.append(d)
        return filtered

    def _object_shape(self, object_name: Optional[str]) -> Dict[str, List[str]]:
        if not object_name:
            return {"properties": [], "methods": []}

        # Проверяем кэш
        if object_name in self._object_shapes_cache:
            return self._object_shapes_cache[object_name]

        try:
            obj = getObject(object_name)
            props_dict = getattr(obj, "properties", {}) if obj else {}
            methods_dict = getattr(obj, "methods", {}) if obj else {}
            props = []
            for name, prop in props_dict.items():
                if not self._is_identifier(name):
                    continue
                p_type = getattr(prop, "type", "")
                desc = getattr(prop, "description", "") or ""
                props.append({"name": name, "type": p_type, "description": desc})
            methods = []
            for name, meth in methods_dict.items():
                if not self._is_identifier(name):
                    continue
                desc = getattr(meth, "description", "") or ""
                methods.append({"name": name, "description": desc})

            shape = {
                "properties": props,
                "methods": methods,
            }

            # Кэшируем результат (ограничиваем размер кэша)
            if len(self._object_shapes_cache) > 50:
                oldest_key = next(iter(self._object_shapes_cache))
                del self._object_shapes_cache[oldest_key]
            self._object_shapes_cache[object_name] = shape

            return shape
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_shape failed for %s: %s", object_name, exc)
            return {"properties": [], "methods": []}

    def _object_properties(self, name: str) -> List[Dict[str, Any]]:
        try:
            obj = getObject(name)
            props_dict = getattr(obj, "properties", {}) if obj else {}
            props: List[Dict[str, Any]] = []
            for key, prop in props_dict.items():
                if not self._is_identifier(key):
                    continue
                p_type = getattr(prop, "type", "") or ""
                desc = getattr(prop, "description", "") or ""
                props.append({
                    "name": key,
                    "type": "property",
                    "signature": "",
                    "doc": f"{desc}\nТип: {p_type}" if p_type else desc,
                    "meta": p_type or "property",
                })
            return props
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_properties failed for %s: %s", name, exc)
            return []

    def _object_info(self, name: str) -> Optional[str]:
        try:
            obj = getObject(name)
            if not obj:
                return None
            desc = getattr(obj, "description", "") or ""
            lines = [f"**{name}**"]
            if desc:
                lines.append("")
                lines.append(desc)
            return "\n".join(lines)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_info failed for %s: %s", name, exc)
            return None

    def _object_property_info(self, obj_name: str, prop_name: str) -> Optional[str]:
        try:
            obj = getObject(obj_name)
            if not obj:
                return None
            prop = getattr(obj, "properties", {}).get(prop_name)
            if not prop:
                return None
            p_type = getattr(prop, "type", "") or ""
            desc = getattr(prop, "description", "") or ""
            lines = [f"**{prop_name}**"]
            if desc:
                lines.append("")
                lines.append(desc)
            if p_type:
                lines.append("")
                lines.append(f"Type: `{p_type}`")
            return "\n".join(lines)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_property_info failed for %s.%s: %s", obj_name, prop_name, exc)
            return None

    def _object_methods(self, name: str) -> List[Dict[str, Any]]:
        try:
            obj = getObject(name)
            methods_dict = getattr(obj, "methods", {}) if obj else {}
            methods: List[Dict[str, Any]] = []
            for key, meth in methods_dict.items():
                if not self._is_identifier(key):
                    continue
                desc = getattr(meth, "description", "") or ""
                methods.append({
                    "name": key,
                    "type": "method",
                    "signature": "()",
                    "doc": desc,
                    "meta": "method",
                })
            return methods
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_methods failed for %s: %s", name, exc)
            return []

    def _object_method_info(self, obj_name: str, method_name: str) -> Optional[str]:
        try:
            obj = getObject(obj_name)
            if not obj:
                return None
            meth = getattr(obj, "methods", {}).get(method_name)
            if not meth:
                return None
            desc = getattr(meth, "description", "") or ""
            lines = [f"**{method_name}**"]
            if desc:
                lines.append("")
                lines.append(desc)
            return "\n".join(lines) if lines else None
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_method_info failed for %s.%s: %s", obj_name, method_name, exc)
            return None

    def _shape_completions(self, shape: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for p in shape.get("properties", []):
            name = p.get("name")
            if not self._is_identifier(name):
                continue
            p_type = p.get("type") or ""
            desc = p.get("description") or ""
            doc_lines = []
            if desc:
                doc_lines.append(desc)
            if p_type:
                doc_lines.append(f"Тип: {p_type}")
            items.append({
                "name": name,
                "type": "property",
                "signature": "",
                "doc": "\n".join(doc_lines),
                "meta": p_type or "property",
            })
        for m in shape.get("methods", []):
            name = m.get("name")
            if not self._is_identifier(name):
                continue
            desc = m.get("description") or ""
            items.append({
                "name": name,
                "type": "method",
                "signature": "()",
                "doc": desc,
                "meta": "method",
            })
        return items

    def _filter_private_items(self, items: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
        if prefix.startswith("_"):
            return items
        filtered = []
        for itm in items:
            nm = itm.get("name") or itm.get("label") or ""
            if isinstance(nm, str) and nm.startswith("_"):
                continue
            filtered.append(itm)
        return filtered

    def _drop_prelude_diags(self, diags: List[Dict[str, Any]], line_offset: int) -> List[Dict[str, Any]]:
        if line_offset <= 0:
            return diags
        filtered: List[Dict[str, Any]] = []
        for d in diags or []:
            rng = d.get("range") or {}
            start = rng.get("start") or {}
            if (start.get("line") or 0) < line_offset:
                continue
            filtered.append(d)
        return filtered

    def _object_name_completions(self, prefix: str, quote: str, in_string: bool) -> List[Dict[str, Any]]:
        try:
            # Проверяем кэш объектов
            if self._object_completions_cache is None:
                objects_storage.preload_objects()
                items = []
                for name, obj in objects_storage.items():
                    if not isinstance(name, str):
                        continue
                    desc = getattr(obj, "description", "") or ""
                    items.append({
                        "name": name,
                        "type": "object",
                        "signature": "",
                        "doc": desc,
                        "meta": "object osysHome",
                        "fullObjectName": name,
                    })
                self._object_completions_cache = items

            # Фильтруем по префиксу
            items = []
            for item in self._object_completions_cache:
                if item["name"].lower().startswith(prefix.lower()):
                    insert = item["name"]
                    if not in_string:
                        insert = f'{quote}{item["name"]}{quote}'
                    completion_item = item.copy()
                    completion_item["insertText"] = insert
                    items.append(completion_item)

            return items
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("lsp object_name_completions failed: %s", exc)
            return []

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.pending = {}  # id -> dict | list
        self.pending_cond = threading.Condition(self.lock)
        self.diag_store: Dict[str, List[Dict[str, Any]]] = {}
        self.next_id = 1
        self.uri = self._make_uri()
        self.version = 0
        self.running = False
        self.stderr_lines: deque[str] = deque(maxlen=50)

        # Кэши для оптимизации производительности
        self._prepared_code_cache: Dict[Tuple[str, Optional[str]], Tuple[str, int]] = {}
        self._completion_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._hover_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self._context_cache: Dict[str, Optional[Tuple[str, str, bool, Optional[str]]]] = {}
        self._object_completions_cache: Optional[List[Dict[str, Any]]] = None
        self._object_shapes_cache: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
        self._last_document_text: Optional[str] = None
        self._last_document_version: int = 0

    def _make_uri(self) -> str:
        tmp = os.path.join(tempfile.gettempdir(), "pylsp_inline.py")
        return f"file:///{tmp.replace(os.sep, '/')}"

    def start(self):
        if self.running:
            # если процесс упал, перезапустим
            if self.proc and self.proc.poll() is None:
                return
            self.running = False
        try:
            lsp_path = os.path.join(os.path.dirname(sys.executable), "pylsp")
            self.proc = subprocess.Popen(
                [lsp_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except FileNotFoundError:
            logger.error("⚠ pylsp not found. Install with: pip install python-lsp-server[all]")
            raise
        logger.info("ℹ starting pylsp --stdio")

        self.running = True
        # stderr reader
        if self.proc.stderr:
            threading.Thread(target=self._stderr_reader, daemon=True).start()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

        # initialize
        self._request("initialize", {
            "processId": os.getpid(),
            "rootUri": None,
            "capabilities": {
                "textDocument": {
                    "completion": {"completionItem": {"documentationFormat": ["markdown", "plaintext"]}},
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                }
            },
            "workspaceFolders": None,
        }, timeout=15.0)
        self._notify("initialized", {})
        # Настройка pylsp: игнорировать W292 (no newline at end of file)
        self._notify("workspace/didChangeConfiguration", {
            "settings": {
                "pylsp": {
                    "plugins": {
                        "pycodestyle": {
                            "ignore": ["W292"],
                            "maxLineLength": 160
                        }
                    }
                }
            }
        })

    def _reader_loop(self):
        assert self.proc and self.proc.stdout
        stdout = self.proc.stdout

        while True:
            # Читаем заголовки
            header = b""
            while b"\r\n\r\n" not in header:
                chunk = stdout.readline()
                if not chunk:
                    return
                header += chunk
            try:
                headers = header.decode("utf-8").split("\r\n")
                content_length = 0
                for h in headers:
                    if h.lower().startswith("content-length"):
                        content_length = int(h.split(":")[1].strip())
                        break
                if content_length == 0:
                    continue
                body = stdout.read(content_length)
                if not body:
                    continue
                message = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
                logger.warning("⚠ pylsp reader error: %s", e)
                continue

            with self.pending_cond:
                if "id" in message and ("result" in message or "error" in message):
                    self.pending[message["id"]] = message
                    self.pending_cond.notify_all()
                elif message.get("method") == "textDocument/publishDiagnostics":
                    params = message.get("params", {})
                    uri = params.get("uri")
                    if uri:
                        self.diag_store[uri] = params.get("diagnostics", [])
                        self.pending_cond.notify_all()

    def _stderr_reader(self):
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            try:
                text = line.decode("utf-8", errors="ignore").rstrip()
            except AttributeError:
                text = str(line).rstrip()
            if text:
                self.stderr_lines.append(text)
                # Логируем свежие строки stderr
                logger.warning("pylsp stderr: %s", text)

    def _write(self, payload: Dict[str, Any]):
        # гарантируем, что процесс жив
        if not self.proc or self.proc.poll() is not None or not self.proc.stdin:
            self.running = False
            self.start()
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("pylsp process is not started")
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8")
        try:
            self.proc.stdin.write(header + raw)
            self.proc.stdin.flush()
        except OSError as e:
            # если пайп сломался — перезапускаем и пробуем один раз
            self.running = False
            self.start()
            if not self.proc or not self.proc.stdin:
                raise RuntimeError("pylsp process is not started") from e
            self.proc.stdin.write(header + raw)
            self.proc.stdin.flush()

    def debug_info(self) -> str:
        rc = self.proc.poll() if self.proc else None
        tail = "\n".join(list(self.stderr_lines)[-5:])
        cache_info = f"caches: prepared={len(self._prepared_code_cache)}, completion={len(self._completion_cache)}, hover={len(self._hover_cache)}, context={len(self._context_cache)}, shapes={len(self._object_shapes_cache)}"
        return f"running={self.running} returncode={rc}\n{cache_info}\nstderr tail:\n{tail}"

    def clear_caches(self):
        """Очищает все кэши для освобождения памяти"""
        self._prepared_code_cache.clear()
        self._completion_cache.clear()
        self._hover_cache.clear()
        self._context_cache.clear()
        self._object_completions_cache = None
        self._object_shapes_cache.clear()
        logger.debug("lsp caches cleared")

    def _request(self, method: str, params: Dict[str, Any], timeout: float = 5.0) -> Any:
        with self.lock:
            msg_id = self.next_id
            self.next_id += 1
            self._write({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})

            # ждём ответа
            start = time.time()
            while True:
                remaining = timeout - (time.time() - start)
                if remaining <= 0:
                    raise TimeoutError(f"pylsp timeout on {method}")
                self.pending_cond.wait(timeout=remaining)
                if msg_id in self.pending:
                    resp = self.pending.pop(msg_id)
                    if "error" in resp:
                        raise RuntimeError(resp["error"])
                    return resp.get("result")

    def _notify(self, method: str, params: Dict[str, Any]):
        with self.lock:
            self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def update_document(self, text: str):
        self.start()
        with self.lock:
            # Проверяем, изменился ли текст документа
            if self._last_document_text == text and self.version > 0:
                return  # Документ не изменился, пропускаем обновление

            self.version += 1
            self._last_document_text = text
            self._last_document_version = self.version

            # Очищаем кэши, так как документ изменился
            self._completion_cache.clear()
            self._hover_cache.clear()
            self._context_cache.clear()
            # Очищаем старую диагностику, чтобы получить свежую от сервера
            self.diag_store.pop(self.uri, None)

            params = {
                "textDocument": {
                    "uri": self.uri,
                    "languageId": "python",
                    "version": self.version,
                },
                "contentChanges": [{"text": text}],
            }
            if self.version == 1:
                # didOpen
                self._write({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": self.uri,
                            "languageId": "python",
                            "version": self.version,
                            "text": text,
                        }
                    }
                })
            else:
                # didChange
                self._write({
                    "jsonrpc": "2.0",
                    "method": "textDocument/didChange",
                    "params": params
                })

    def completion(self, text: str, line: int, column: int) -> List[Dict[str, Any]]:
        # Создаем ключ для кэширования
        cache_key = f"{hash(text)}:{line}:{column}:{self._last_document_version}"

        # Проверяем кэш
        if cache_key in self._completion_cache:
            return self._completion_cache[cache_key]

        self.update_document(text)
        result = self._request("textDocument/completion", {
            "textDocument": {"uri": self.uri},
            "position": {"line": line - 1, "character": column},
        }) or {}
        items = result.get("items", result) if isinstance(result, dict) else result
        mapped_items = self._map_completions(items)

        # Кэшируем результат (ограничиваем размер кэша)
        if len(self._completion_cache) > 50:
            # Удаляем самый старый элемент
            oldest_key = next(iter(self._completion_cache))
            del self._completion_cache[oldest_key]

        self._completion_cache[cache_key] = mapped_items
        return mapped_items

    def hover(self, text: str, line: int, column: int) -> Optional[Dict[str, Any]]:
        # Создаем ключ для кэширования
        cache_key = f"{hash(text)}:{line}:{column}:{self._last_document_version}"

        # Проверяем кэш
        if cache_key in self._hover_cache:
            return self._hover_cache[cache_key]

        self.update_document(text)
        result = self._request("textDocument/hover", {
            "textDocument": {"uri": self.uri},
            "position": {"line": line - 1, "character": column},
        })

        hover_result = None
        if result:
            contents = result.get("contents")
            value = ""
            if isinstance(contents, dict):
                value = contents.get("value") or ""
            elif isinstance(contents, list):
                value = "\n".join(c.get("value", c) if isinstance(c, dict) else str(c) for c in contents)
            else:
                value = str(contents)
            rng = result.get("range")
            hover_result = {"contents": value, "range": rng}

        # Кэшируем результат (ограничиваем размер кэша)
        if len(self._hover_cache) > 50:
            # Удаляем самый старый элемент
            oldest_key = next(iter(self._hover_cache))
            del self._hover_cache[oldest_key]

        self._hover_cache[cache_key] = hover_result
        return hover_result

    def diagnostics(self, text: str, timeout: float = 2.5) -> List[Dict[str, Any]]:
        self.update_document(text)
        # ждём publishDiagnostics
        until = time.time() + timeout
        with self.pending_cond:
            while time.time() < until:
                self.pending_cond.wait(timeout=0.2)
                if self.uri in self.diag_store:
                    diags = self.diag_store.get(self.uri, [])
                    logger.debug("lsp diagnostics: got %d diagnostics after document update", len(diags))
                    return diags
        # Если не дождались - возвращаем пустой список вместо старой диагностики
        logger.debug("lsp diagnostics: timeout waiting for fresh diagnostics")
        return []

    def signature_help(self, text: str, line: int, column: int) -> Optional[Dict[str, Any]]:
        self.update_document(text)
        result = self._request("textDocument/signatureHelp", {
            "textDocument": {"uri": self.uri},
            "position": {"line": line - 1, "character": column},
        })
        if not result or not result.get("signatures"):
            return None
        active_sig = result.get("activeSignature", 0) or 0
        active_param = result.get("activeParameter", 0) or 0
        sigs = result.get("signatures", [])
        sig = sigs[active_sig] if active_sig < len(sigs) else sigs[0]
        label = sig.get("label", "")
        doc = sig.get("documentation", "")
        if isinstance(doc, dict):
            doc = doc.get("value", "")
        params = sig.get("parameters", [])
        return {
            "label": label,
            "doc": doc or "",
            "activeParameter": active_param,
            "parameters": [p.get("label", "") for p in params]
        }

    def _map_completions(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kind_map = {
            2: "module",
            3: "function",
            4: "constructor",
            5: "field",
            6: "variable",
            7: "class",
            8: "interface",
            9: "module",
            10: "property",
            14: "keyword",
        }
        result = []
        for itm in items[:50]:
            label = itm.get("label", "")
            detail = itm.get("detail", "")
            documentation = itm.get("documentation", "")
            if isinstance(documentation, dict):
                documentation = documentation.get("value", "")
            result.append({
                "name": label,
                "type": kind_map.get(itm.get("kind"), "text"),
                "signature": detail or "",
                "doc": documentation or "",
                "meta": kind_map.get(itm.get("kind"), "text")
            })
        return result


# Один общий клиент для всего приложения
pylsp_client = PylspClient()


# pylint: disable=protected-access
def run_lsp_action(
    action: str,
    code: str,
    line: Optional[int] = None,
    column: Optional[int] = None,
    timeout: float = 2.5,
    object_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Выполняет действие LSP и возвращает унифицированный ответ для API / WS.
    Args:
        action: completion | hover | diagnostics | signature
        code: исходный код
        line: номер строки (1-based)
        column: номер колонки (0-based)
        timeout: таймаут для diagnostics
    """
    normalized_action = (action or "").lower()
    safe_line = max(1, int(line or 1))
    safe_column = max(0, int(column or 0))
    obj_shape = pylsp_client._object_shape(object_name)
    prepared_code, line_offset = pylsp_client._prepare_lsp_code(code, object_name)
    adj_line = safe_line + line_offset

    if normalized_action == "completion":
        items = pylsp_client.completion(prepared_code, adj_line, safe_column)
        # Дополняем подсказками из shape, чтобы у методов был description
        prefix = pylsp_client._prefix_at(code, safe_line, safe_column)
        if obj_shape and object_name and pylsp_client._is_self_context(code, safe_line, safe_column):
            items = pylsp_client._shape_completions(obj_shape) + items
        gp_ctx = pylsp_client._getproperty_context(code, safe_line, safe_column)
        if gp_ctx:
            items = []
            gp_prefix, gp_quote, gp_in_string, gp_obj = gp_ctx
            if gp_obj:
                # Проверяем, есть ли в префиксе точка (например, для self.getProperty("obj.property"))
                if "." in gp_prefix:
                    # Извлекаем имя объекта из начала префикса
                    obj_name_from_prefix = gp_prefix.split(".")[0]
                    # Если obj_name_from_prefix == "self", заменяем на object_name
                    actual_obj_name = object_name if obj_name_from_prefix == "self" and object_name else obj_name_from_prefix
                    items = pylsp_client._object_properties(actual_obj_name) + items
                else:
                    # Для self.getProperty("property") или obj.getProperty("property") - свойства указанного объекта
                    # Если gp_obj == "self", заменяем на object_name
                    actual_obj_name = object_name if gp_obj == "self" and object_name else gp_obj
                    items = pylsp_client._object_properties(actual_obj_name) + items
            else:
                # Проверяем, есть ли в префиксе точка (например, "объект.")
                if "." in gp_prefix:
                    # Извлекаем имя объекта из начала префикса
                    obj_name_from_prefix = gp_prefix.split(".")[0]
                    # Если obj_name_from_prefix == "self", заменяем на object_name
                    actual_obj_name = object_name if obj_name_from_prefix == "self" and object_name else obj_name_from_prefix
                    items = pylsp_client._object_properties(actual_obj_name) + items
                else:
                    items = pylsp_client._object_name_completions(gp_prefix, gp_quote, gp_in_string) + items
        # Обработка callMethod("объект.метод")
        cm_ctx = pylsp_client._callmethod_context(code, safe_line, safe_column)
        if cm_ctx:
            items = []
            cm_prefix, cm_quote, cm_in_string, cm_obj = cm_ctx
            if cm_obj:
                # Проверяем, есть ли в префиксе точка (например, для self.callMethod("obj.method"))
                if "." in cm_prefix:
                    # Извлекаем имя объекта из начала префикса
                    obj_name_from_prefix = cm_prefix.split(".")[0]
                    # Если obj_name_from_prefix == "self", заменяем на object_name
                    actual_obj_name = object_name if obj_name_from_prefix == "self" and object_name else obj_name_from_prefix
                    items = pylsp_client._object_methods(actual_obj_name) + items
                else:
                    # Для self.callMethod("method") или obj.callMethod("method") - методы указанного объекта
                    # Если cm_obj == "self", заменяем на object_name
                    actual_obj_name = object_name if cm_obj == "self" and object_name else cm_obj
                    items = pylsp_client._object_methods(actual_obj_name) + items
            else:
                # Проверяем, есть ли в префиксе точка (например, "объект.")
                if "." in cm_prefix:
                    # Извлекаем имя объекта из начала префикса
                    obj_name_from_prefix = cm_prefix.split(".")[0]
                    # Если obj_name_from_prefix == "self", заменяем на object_name
                    actual_obj_name = object_name if obj_name_from_prefix == "self" and object_name else obj_name_from_prefix
                    items = pylsp_client._object_methods(actual_obj_name) + items
                else:
                    items = pylsp_client._object_name_completions(cm_prefix, cm_quote, cm_in_string) + items

        items = pylsp_client._filter_private_items(items, prefix)
        return {"action": "completion", "items": items}

    if normalized_action == "hover":
        hover = pylsp_client.hover(prepared_code, adj_line, safe_column)
        if hover and hover.get("range"):
            hover["range"] = pylsp_client._shift_range(hover.get("range"), line_offset)
        if not hover or not hover.get("contents"):
            word = pylsp_client._word_at(code, safe_line, safe_column)

            # Сначала проверяем, находится ли курсор на члене объекта (object.member)
            # Применяем только если есть self и указан object_name
            if object_name:
                member_ctx = pylsp_client._object_member_context(code, safe_line, safe_column)
                if member_ctx:
                    obj_name, member_name = member_ctx
                    # Применяем только для self
                    if obj_name == "self":
                        # Проверяем, является ли это свойством
                        obj = pylsp_client._object_shape(object_name)
                        if obj and obj.get("properties"):
                            for prop in obj["properties"]:
                                if prop.get("name") == member_name:
                                    info = pylsp_client._object_property_info(object_name, member_name)
                                    hover = {"contents": info}
                                    break

                        # Если не нашли как свойство, проверяем как метод
                        if (not hover or not hover.get("contents")) and obj and obj.get("methods"):
                            for meth in obj["methods"]:
                                if meth.get("name") == member_name:
                                    info = pylsp_client._object_method_info(object_name, member_name)
                                    hover = {"contents": info}
                                    break

            # Если не нашли в контексте object.member, проверяем старые случаи (внутри аргументов функций)
            if not hover or not hover.get("contents"):
                gp_arg = pylsp_client._call_arg_at_cursor(code=code, line=safe_line, col=safe_column)
                if gp_arg:
                    if gp_arg['object'] == 'self':
                        gp_arg['object'] = object_name
                    if gp_arg['object'] == word:
                        info = pylsp_client._object_info(gp_arg['object'])
                        hover = {"contents": info}
                    elif gp_arg.get('property') == word:
                        info = pylsp_client._object_property_info(gp_arg['object'], gp_arg['property'])
                        hover = {"contents": info}
                    elif gp_arg.get('method') == word:
                        info = pylsp_client._object_method_info(gp_arg['object'], gp_arg['method'])
                        hover = {"contents": info}
                
        return {"action": "hover", "hover": hover}

    if normalized_action == "diagnostics":
        diags = pylsp_client.diagnostics(prepared_code, timeout=timeout)
        shifted = []
        for diag in diags:
            rng = pylsp_client._shift_range(diag.get("range"), line_offset)
            if rng:
                diag = dict(diag)
                diag["range"] = rng
            shifted.append(diag)
        return {"action": "diagnostics", "diagnostics": pylsp_client._filter_diagnostics(shifted)}

    if normalized_action == "signature":
        sig = pylsp_client.signature_help(prepared_code, adj_line, safe_column)
        return {"action": "signature", "signature": sig}

    raise ValueError(f"Unsupported LSP action: {action}")
