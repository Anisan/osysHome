import os
import json
import re
from collections import defaultdict

def find_translation_keys(project_dir):
    """Находит все ключи переводов, разделяя их по модулям и выявляет общие ключи"""
    # Регулярные выражения для поиска переводов
    patterns = [
        r'_\(["\'](.+?)["\']\)',          # _('text')
        r'gettext\(["\'](.+?)["\']\)',    # gettext('text')
        r'get_translation\(["\'](.+?)["\']',  # get_translation('text')
        r'{{ _\(["\'](.+?)["\']\) }}',    # {{ _('text') }}
        r'{{\s*get_translation\(["\'](.+?)["\']',  # {{ get_translation('text') }}
    ]
    
    # Сначала собираем все ключи и подсчитываем их частоту
    all_keys = defaultdict(list)
    
    # Сканируем основное приложение (app)
    app_dir = os.path.join(project_dir, 'app')
    for root, dirs, files in os.walk(app_dir):
        for file in files:
            if file.endswith(('.py', '.html')):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern in patterns:
                        for match in re.finditer(pattern, content):
                            if match.group(1):
                                key = match.group(1)
                                if 'app' not in all_keys[key]:
                                    all_keys[key].append('app')
    
    # Сканируем плагины (plugins)
    plugins_dir = os.path.join(project_dir, 'plugins')
    if os.path.exists(plugins_dir):
        for plugin in os.listdir(plugins_dir):
            plugin_dir = os.path.join(plugins_dir, plugin)
            if os.path.isdir(plugin_dir):
                for root, dirs, files in os.walk(plugin_dir):
                    for file in files:
                        if file.endswith(('.py', '.html')):
                            filepath = os.path.join(root, file)
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                                for pattern in patterns:
                                    for match in re.finditer(pattern, content):
                                        if match.group(1):
                                            key = match.group(1)
                                            if plugin not in all_keys[key]:
                                                all_keys[key].append(plugin)
    
    # Определяем ключи, которые встречаются в нескольких модулях (минимум в 5)
    common_keys = {key for key, modules in all_keys.items() if len(modules) >= 2}
    
    # Распределяем ключи по модулям
    final_keys = defaultdict(set)
    
    # Все общие ключи идут в app
    for key in common_keys:
        final_keys['app'].add(key)
    
    # Остальные ключи распределяем по их исходным модулям
    for key, modules in all_keys.items():
        if key not in common_keys:
            for module in set(modules):  # используем set чтобы избежать дубликатов
                final_keys[module].add(key)
    
    return {k: sorted(list(v)) for k, v in final_keys.items()}

def create_translation_files(keys, project_dir, languages):
    """Создает файлы переводов для каждого модуля"""
    # Создаем переводы для основного приложения (app)
    app_translations_dir = os.path.join(project_dir, 'app', 'translations')
    os.makedirs(app_translations_dir, exist_ok=True)
    
    for lang in languages:
        # Файл перевода для app
        app_file = os.path.join(app_translations_dir, f'{lang}.json')
        app_translations = {}
        
        if os.path.exists(app_file):
            with open(app_file, 'r', encoding='utf-8') as f:
                app_translations = json.load(f)
        
        # Обновляем переводы для app
        app_keys = {}
        for key in keys.get('app', []):
            app_keys[key] = key if lang == 'en' else ''
            if key in app_translations:
                app_keys[key] = app_translations[key]
        
        with open(app_file, 'w', encoding='utf-8') as f:
            json.dump(app_keys, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f'Updated app translations: {app_file}')
    
    # Создаем переводы для плагинов
    plugins_dir = os.path.join(project_dir, 'plugins')
    for plugin in keys:
        if plugin == 'app':
            continue
            
        plugin_translations_dir = os.path.join(plugins_dir, plugin, 'translations')
        os.makedirs(plugin_translations_dir, exist_ok=True)
        
        for lang in languages:
            plugin_file = os.path.join(plugin_translations_dir, f'{lang}.json')
            plugin_translations = {}
            
            if os.path.exists(plugin_file):
                with open(plugin_file, 'r', encoding='utf-8') as f:
                    plugin_translations = json.load(f)
            
            plugin_keys = {}
            for key in keys.get(plugin, []):
                plugin_keys[key] = key if lang == 'en' else ''
                if key in plugin_translations:
                    plugin_keys[key] = plugin_translations[key]
            
            with open(plugin_file, 'w', encoding='utf-8') as f:
                json.dump(plugin_keys, f, ensure_ascii=False, indent=2, sort_keys=True)
            print(f'Updated {plugin} translations: {plugin_file}')

if __name__ == '__main__':
    project_dir = os.path.dirname(os.path.abspath(__file__))
    languages = ['en', 'ru']  # Поддерживаемые языки
    
    # Находим все ключи переводов
    translation_keys = find_translation_keys(project_dir)
    
    # Создаем/обновляем файлы переводов
    create_translation_files(translation_keys, project_dir, languages)
    
    print("Translation files have been updated successfully!")