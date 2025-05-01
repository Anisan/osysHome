# Используйте официальный образ Python
FROM python:3.10

# Установите переменную окружения для улучшения вывода
ENV PYTHONUNBUFFERED 1

# Установите зависимости ОС
RUN apt-get update && apt-get install -y \
    #vlc \
    #libvlc-dev \
    #ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установите рабочую директорию в контейнере
WORKDIR /app

# Создайте папку plugins
RUN mkdir -p /app/plugins

# Клонируйте репозитории в папку plugins
RUN git clone https://github.com/Anisan/osysHome-Modules.git /app/plugins/Modules && \
    git clone https://github.com/Anisan/osysHome-Objects.git /app/plugins/Objects && \
    git clone https://github.com/Anisan/osysHome-Users.git /app/plugins/Users && \
    git clone https://github.com/Anisan/osysHome-Scheduler.git /app/plugins/Scheduler && \
    git clone https://github.com/Anisan/osysHome-wsServer.git /app/plugins/wsServer && \
    git clone https://github.com/Anisan/osysHome-Dashboard.git /app/plugins/Dashboard

# Копирование файла настройки
COPY settings_sample.py /app/settings.py

# Скопируйте зависимости и установите их
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Создание документации
RUN pdoc --docformat google --no-show-source --output-dir docs settings_sample.py app plugins

# Скопируйте остальные файлы приложения
COPY . /app/

# Запустите ваше приложение
CMD ["python", "main.py"]
