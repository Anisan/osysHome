# Используйте официальный образ Python
FROM python:3.10

# Установите переменную окружения для улучшения вывода
ENV PYTHONUNBUFFERED 1

# Установите зависимости ОС
RUN apt-get update && apt-get install -y \
    vlc \
    libvlc-dev \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установите рабочую директорию в контейнере
WORKDIR /app

# Копирование файла настройки
COPY settings_sample.py /app/settings.py

# Скопируйте зависимости и установите их
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Скопируйте остальные файлы приложения
COPY . /app/

# Запустите ваше приложение
CMD ["python", "main.py"]
