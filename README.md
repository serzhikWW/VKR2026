# Система детекции огня и дыма

Полноценное веб-приложение для детекции огня и дыма на видеозаписях с использованием YOLO26s.

---

## Архитектура

```
┌─────────────────────────────────────────────────┐
│              Уровень представления               │
│         React + Vite (порт 3000)                │
└──────────────────┬──────────────────────────────┘
                   │ HTTP / WebSocket
┌──────────────────▼──────────────────────────────┐
│          FastAPI Backend (порт 8000)             │
│  /api/videos   /api/detections   /ws/progress   │
└────────┬────────────┬───────────────────────────┘
         │            │
┌────────▼──┐  ┌──────▼────────┐  ┌──────────────┐
│ PostgreSQL │  │  Celery Worker│  │    MinIO S3  │
│  :5432    │  │  (YOLO26s)    │  │   :9000/9001 │
└───────────┘  └───────────────┘  └──────────────┘
                       │
               ┌───────▼───────┐
               │     Redis     │
               │     :6379     │
               └───────────────┘
```

---

## Стек технологий

| Компонент | Технология |
|-----------|------------|
| Фронтенд | React 18, Vite, Recharts |
| Бэкенд | FastAPI, SQLAlchemy async |
| Детекция | YOLO26s (ultralytics) + OpenCV |
| Очередь задач | Celery + Redis |
| БД результатов | PostgreSQL 15 |
| БД видео | MinIO (S3-совместимое) |
| Контейнеризация | Docker Compose |

---

## Быстрый старт

### 1. Разместите модель

Поместите файл `yolo26s.pt` в папку `backend/models/`:

```bash
mkdir -p backend/models
cp /path/to/yolo26s.pt backend/models/
```

> **Без модели** — приложение запустится в **демо-режиме** с имитацией детекций.

### 2. Запустите через Docker Compose

```bash
docker compose up --build
```

При первом запуске скачиваются образы и устанавливаются зависимости (~5–10 минут).

### 3. Откройте приложение

| Сервис | URL |
|--------|-----|
| Веб-интерфейс | http://localhost:3000 |
| API документация | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |

**MinIO логин:** `minioadmin` / `minioadmin123`

---

## Использование

1. Откройте **http://localhost:3000**
2. Перейдите в раздел **«Загрузка видео»**
3. Перетащите видеофайл (MP4, AVI, MOV, MKV, WEBM — до 500 МБ)
4. Нажмите **«Начать анализ»**
5. Наблюдайте прогресс обработки в реальном времени через WebSocket
6. После завершения перейдите к результатам:
   - Общая статистика детекций
   - График событий по времени
   - Список всех детекций с координатами bbox
   - Аннотированное видео с наложенными рамками

---

## Структура проекта

```
VKR2026/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI приложение
│       ├── worker.py            # Celery задачи
│       ├── core/
│       │   ├── config.py        # Настройки
│       │   ├── database.py      # SQLAlchemy async
│       │   └── minio_client.py  # MinIO клиент
│       ├── models/
│       │   └── models.py        # ORM модели (Video, Detection, Summary)
│       ├── schemas/
│       │   └── schemas.py       # Pydantic схемы
│       ├── api/
│       │   ├── videos.py        # REST API видео
│       │   ├── detections.py    # REST API детекций
│       │   └── websocket.py     # WebSocket прогресс
│       └── services/
│           ├── detection_service.py  # YOLO обработка
│           └── storage_service.py   # MinIO операции
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── styles/globals.css
│       ├── services/api.js
│       ├── components/
│       │   ├── Layout.jsx
│       │   └── Layout.module.css
│       └── pages/
│           ├── Dashboard.jsx        # Главный дашборд
│           ├── Upload.jsx           # Загрузка с прогрессом
│           ├── VideoList.jsx        # Архив видео
│           └── VideoDetail.jsx      # Детальный анализ
```

---

## API Endpoints

### Видео
| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/videos/upload` | Загрузить видео |
| `GET` | `/api/videos/` | Список видео |
| `GET` | `/api/videos/{id}` | Детали видео |
| `DELETE` | `/api/videos/{id}` | Удалить видео |

### Детекции
| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/detections/video/{id}` | Список детекций |
| `GET` | `/api/detections/summary/{id}` | Сводка по видео |
| `GET` | `/api/detections/stats/overview` | Общая статистика |

### WebSocket
| Путь | Описание |
|------|----------|
| `WS /ws/progress/{video_id}` | Прогресс обработки в реальном времени |

---

## Настройка модели

Переменные окружения (`.env` или `docker-compose.yml`):

```env
MODEL_PATH=/app/models/yolo26s.pt
CONFIDENCE_THRESHOLD=0.25   # Порог уверенности
IOU_THRESHOLD=0.45           # IoU для NMS
FRAME_SKIP=2                 # Обрабатывать каждый N-й кадр
```

---

## База данных

### PostgreSQL — результаты анализа

| Таблица | Описание |
|---------|----------|
| `videos` | Метаданные видеозаписей |
| `detections` | Каждая детекция (bbox, метка, уверенность) |
| `detection_summaries` | Агрегированная статистика по видео |

### MinIO — видеохранилище

| Бакет | Содержимое |
|-------|------------|
| `videos` | Оригинальные загруженные видео |
| `results` | Аннотированные видео с bbox |
