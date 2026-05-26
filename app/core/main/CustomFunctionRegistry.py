"""In-memory registry of user CustomFunction code with hot reload."""

import functools
import inspect
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from app.database import session_scope
from app.logging_config import getLogger

_logger = getLogger('custom_function_registry')


def _invalidate_lsp_caches() -> None:
    try:
        from app.core.lsp_client import pylsp_client
        pylsp_client.clear_caches()
    except Exception:
        pass


def _invalidate_execution_cache() -> None:
    try:
        from app.core.lib.execute import invalidate_execution_environment_cache
        invalidate_execution_environment_cache()
    except Exception:
        pass


class CustomFunctionRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._bindings: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}
        self._symbols_by_cf: Dict[str, Set[str]] = {}
        self._symbol_owner: Dict[str, str] = {}
        self._intelli_cache: List[dict] = []
        self._lsp_prelude_lines: List[str] = []
        self._lsp_revision: int = 0

    def load_all(self) -> None:
        from app.core.models.CustomFunctions import CustomFunction

        with session_scope() as session:
            rows = (
                session.query(CustomFunction)
                .filter(CustomFunction.active.is_(True))
                .order_by(CustomFunction.order.asc(), CustomFunction.name.asc())
                .all()
            )
            snapshot = [
                {
                    'name': r.name,
                    'code': r.code or '',
                    'description': r.description or '',
                }
                for r in rows
            ]
        self._rebuild_all(snapshot)

    def reload(self, name: str, precompiled: Optional[Dict[str, Any]] = None) -> bool:
        from app.core.models.CustomFunctions import CustomFunction

        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if not row:
                with self._lock:
                    self._remove_cf_unlocked(name)
                    self._lsp_revision += 1
                self._notify_bindings_changed()
                return False
            if not row.active:
                with self._lock:
                    self._remove_cf_unlocked(name)
                    self._lsp_revision += 1
                self._notify_bindings_changed()
                return True
            payload = {
                'name': row.name,
                'code': row.code or '',
                'description': row.description or '',
            }
        return self._reload_one(payload, precompiled=precompiled)

    def reload_all(self) -> None:
        self.load_all()

    def get_bindings(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._bindings)

    def get_compile_errors(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._errors)

    def get_intelli_cache(self) -> List[dict]:
        with self._lock:
            return list(self._intelli_cache)

    def get_lsp_revision(self) -> int:
        with self._lock:
            return self._lsp_revision

    def get_lsp_prelude_lines(self, exclude_name: Optional[str] = None) -> List[str]:
        with self._lock:
            raw = list(self._lsp_prelude_lines)
        if not exclude_name:
            return raw
        filtered: List[str] = []
        skip_block = False
        for line in raw:
            if line.startswith("# CustomFunction:"):
                cf_name = line.split(":", 1)[1].strip()
                skip_block = cf_name == exclude_name
                if skip_block:
                    continue
                filtered.append(line)
                continue
            if skip_block:
                continue
            filtered.append(line)
        return filtered

    def get_exported_symbols(self, name: str) -> Set[str]:
        with self._lock:
            return set(self._symbols_by_cf.get(name, set()))

    def validate_exported_symbols(
        self, name: str, code: str, active: bool = True
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        if not active:
            return True, None, None
        bindings, err = self._compile_one(name, code)
        if err:
            return False, err, None
        with self._lock:
            for symbol in bindings:
                owner = self._symbol_owner.get(symbol)
                if owner and owner != name:
                    return False, (
                        f"Symbol '{symbol}' is already exported by CustomFunction '{owner}'"
                    ), None
        return True, None, bindings

    def _notify_bindings_changed(self) -> None:
        _invalidate_lsp_caches()
        _invalidate_execution_cache()
        self._sync_app_intelli_extension()

    def _rebuild_all(self, rows: List[dict]) -> None:
        bindings: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        symbols_by_cf: Dict[str, Set[str]] = {}
        symbol_owner: Dict[str, str] = {}
        intelli: List[dict] = []

        for row in rows:
            cf_name = row['name']
            cf_bindings, err = self._compile_one(cf_name, row['code'])
            if err:
                errors[cf_name] = err
                _logger.error("CustomFunction '%s' compile error: %s", cf_name, err)
                continue
            conflict = None
            for symbol in cf_bindings:
                if symbol in symbol_owner:
                    conflict = (
                        f"Symbol '{symbol}' conflicts with CustomFunction "
                        f"'{symbol_owner[symbol]}'"
                    )
                    break
            if conflict:
                errors[cf_name] = conflict
                _logger.error("CustomFunction '%s': %s", cf_name, conflict)
                continue
            symbols_by_cf[cf_name] = set(cf_bindings.keys())
            for symbol, value in cf_bindings.items():
                symbol_owner[symbol] = cf_name
                bindings[symbol] = value
            intelli.extend(
                self._build_intelli_for_cf(cf_name, cf_bindings, row.get('description', ''))
            )

        prelude_lines = self._build_lsp_prelude_lines(rows)
        with self._lock:
            self._bindings = bindings
            self._errors = errors
            self._symbols_by_cf = symbols_by_cf
            self._symbol_owner = symbol_owner
            self._intelli_cache = intelli
            self._lsp_prelude_lines = prelude_lines
            self._lsp_revision += 1
        self._notify_bindings_changed()

    def _reload_one(
        self, row: dict, precompiled: Optional[Dict[str, Any]] = None
    ) -> bool:
        cf_name = row['name']
        if precompiled is not None:
            cf_bindings = precompiled
            err = None
        else:
            cf_bindings, err = self._compile_one(cf_name, row['code'])
        with self._lock:
            if err:
                self._errors[cf_name] = err
                _logger.error("CustomFunction '%s' reload failed: %s", cf_name, err)
                return False
            for symbol in cf_bindings:
                owner = self._symbol_owner.get(symbol)
                if owner and owner != cf_name:
                    msg = (
                        f"Symbol '{symbol}' is already exported by CustomFunction '{owner}'"
                    )
                    self._errors[cf_name] = msg
                    _logger.error("CustomFunction '%s': %s", cf_name, msg)
                    return False
            self._remove_cf_unlocked(cf_name)
            self._errors.pop(cf_name, None)
            self._symbols_by_cf[cf_name] = set(cf_bindings.keys())
            for symbol, value in cf_bindings.items():
                self._symbol_owner[symbol] = cf_name
                self._bindings[symbol] = value
            self._rebuild_intelli_unlocked()
            self._rebuild_lsp_prelude_unlocked()
            self._lsp_revision += 1
        self._notify_bindings_changed()
        return True

    def _remove_cf_unlocked(self, name: str) -> None:
        symbols = self._symbols_by_cf.pop(name, set())
        for symbol in symbols:
            if self._symbol_owner.get(symbol) == name:
                del self._symbol_owner[symbol]
                self._bindings.pop(symbol, None)
        self._errors.pop(name, None)
        self._rebuild_intelli_unlocked()
        self._rebuild_lsp_prelude_unlocked()

    def _rebuild_intelli_unlocked(self) -> None:
        from app.core.models.CustomFunctions import CustomFunction

        descriptions: Dict[str, str] = {}
        with session_scope() as session:
            for row in session.query(CustomFunction).all():
                descriptions[row.name] = row.description or ''

        intelli: List[dict] = []
        for cf_name, symbols in self._symbols_by_cf.items():
            cf_bindings = {s: self._bindings[s] for s in symbols if s in self._bindings}
            intelli.extend(
                self._build_intelli_for_cf(
                    cf_name,
                    cf_bindings,
                    descriptions.get(cf_name, ''),
                )
            )
        self._intelli_cache = intelli

    def _rebuild_lsp_prelude_unlocked(self) -> None:
        from app.core.models.CustomFunctions import CustomFunction

        with session_scope() as session:
            rows = (
                session.query(CustomFunction)
                .filter(CustomFunction.active.is_(True))
                .order_by(CustomFunction.order.asc(), CustomFunction.name.asc())
                .all()
            )
            snapshot = [
                {'name': r.name, 'code': r.code or ''}
                for r in rows
            ]
        self._lsp_prelude_lines = self._build_lsp_prelude_lines(snapshot)

    @staticmethod
    def _build_lsp_prelude_lines(rows: List[dict]) -> List[str]:
        lines: List[str] = []
        for row in rows:
            code = (row.get('code') or '').strip()
            if not code:
                continue
            cf_name = row.get('name', '')
            lines.append(f"# CustomFunction: {cf_name}")
            lines.extend(code.splitlines())
            lines.append('')
        return lines

    def _sync_app_intelli_extension(self) -> None:
        try:
            from flask import current_app, has_app_context

            if has_app_context():
                current_app.extensions['custom_function_intelli_cache'] = self.get_intelli_cache()
        except Exception:
            pass

    def _compile_one(self, name: str, code: str) -> Tuple[Dict[str, Any], Optional[str]]:
        from app.core.lib.execute import get_base_module_environment

        if not code or not code.strip():
            return {}, None

        env = get_base_module_environment()
        keys_before = set(env.keys())
        filename = f"<CustomFunction:{name}>"
        try:
            code_obj = compile(code, filename, 'exec')
            exec(code_obj, env)
        except Exception as ex:
            return {}, f"{type(ex).__name__}: {ex}"

        bindings: Dict[str, Any] = {}
        for key in set(env.keys()) - keys_before:
            if key.startswith('_'):
                continue
            value = env[key]
            if inspect.isfunction(value) or inspect.isbuiltin(value):
                bindings[key] = self._wrap_callable(value, name, key)
            else:
                bindings[key] = value
        return bindings, None

    @staticmethod
    def _wrap_callable(fn, cf_name: str, fn_name: str):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapped.__qualname__ = f"{cf_name}.{fn_name}"
        return wrapped

    @staticmethod
    def _build_intelli_for_cf(cf_name: str, bindings: Dict[str, Any], description: str) -> List[dict]:
        items = []
        for symbol, value in bindings.items():
            if inspect.isfunction(value) or inspect.isbuiltin(value):
                sig_target = getattr(value, '__wrapped__', value)
                try:
                    signature = str(inspect.signature(sig_target))
                except (ValueError, TypeError):
                    signature = "()"
                fn_doc = (inspect.getdoc(value) or '').strip()
                desc = (description or '').strip()
                doc_parts = []
                if desc:
                    doc_parts.append(desc)
                if fn_doc and fn_doc != desc:
                    doc_parts.append(fn_doc)
                doc = '\n\n'.join(doc_parts)
                items.append({
                    'type': 'function',
                    'name': symbol,
                    'qualified_name': symbol,
                    'module': f'CustomFunction:{cf_name}',
                    'signature': signature,
                    'doc': doc,
                })
        return items


custom_function_registry = CustomFunctionRegistry()
