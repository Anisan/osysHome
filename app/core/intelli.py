import inspect
import textwrap

def clean_doc(doc):
    if not doc:
        return "Без описания."
    return textwrap.dedent(str(doc)).strip()

def get_signature(obj):
    """Возвращает строку сигнатуры функции/метода, например: (host, port=5432)"""
    try:
        sig = inspect.signature(obj)
        return str(sig)
    except (ValueError, TypeError):
        return "()"

def build_intelli_cache(modules):
    cache = []
    for module in modules:
        for name in dir(module):
            if name.startswith('_'):
                continue
            try:
                obj = getattr(module, name)
            except Exception:
                continue

            # === Функции ===
            if inspect.isfunction(obj) or inspect.isbuiltin(obj):
                doc = clean_doc(getattr(obj, '__doc__', None))
                signature = get_signature(obj)
                cache.append({
                    "type": "function",
                    "name": name,
                    "qualified_name": name,
                    "module": module.__name__,
                    "signature": signature,
                    "doc": doc
                })

            # === Классы ===
            elif inspect.isclass(obj):
                class_doc = clean_doc(getattr(obj, '__doc__', None))
                cache.append({
                    "type": "class",
                    "name": name,
                    "qualified_name": name,
                    "module": module.__name__,
                    "signature": "()",  # классы вызываются как Class()
                    "doc": class_doc
                })

                # === Методы класса ===
                for method_name in dir(obj):
                    if method_name.startswith('_'):
                        continue
                    try:
                        method = getattr(obj, method_name)
                    except Exception:
                        continue

                    # Метод должен быть функцией (не свойством, не данных)
                    if inspect.ismethod(method) or inspect.isfunction(method):
                        method_doc = clean_doc(getattr(method, '__doc__', None))
                        method_signature = get_signature(method)
                        cache.append({
                            "type": "method",
                            "name": method_name,
                            "qualified_name": f"{name}.{method_name}",
                            "class_name": name,
                            "module": module.__name__,
                            "signature": method_signature,
                            "doc": method_doc
                        })
    return cache
