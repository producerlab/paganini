# Paganini Bot

Telegram-бот для парсинга финансовых отчетов Wildberries и экспорта в Excel.

## Возможности

- Парсинг еженедельных финансовых отчетов WB (Россия и СНГ)
- Автоматический расчет всех комиссий и удержаний
- Экспорт в Excel с детализацией по товарам
- Поддержка нескольких магазинов на одном аккаунте
- Реферальная программа с бонусами
- Интеграция с YooKassa для платежей

## Требования

- Python 3.11+
- SQLite

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/producerlab/paganini.git
cd paganini
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` и заполните все необходимые значения:

| Переменная | Описание |
|------------|----------|
| `TOKEN` | Токен Telegram бота от @BotFather |
| `BOT_USERNAME` | Username бота (без @) |
| `ADMIN_IDS` | ID админов через запятую |
| `CHANNEL_USERNAME` | Канал для проверки подписки |
| `CLUB_CHAT_ID` | ID закрытого клуба |
| `DB_URL` | Строка подключения к БД |
| `MEDIA_ROOT` | Путь к медиа-файлам |
| `DATA_ROOT` | Путь для сохранения отчетов |
| `UKASSA_ACCOUNT_ID` | ID магазина YooKassa |
| `UKASSA_SECRET_KEY` | Secret key YooKassa |

### 5. Подготовка медиа-файлов

Создайте папку `media/token/` и добавьте скриншоты инструкции:
- `1.jpg` - `5.jpg` — скриншоты по созданию API-токена WB

### 6. Запуск

```bash
python main.py
```

## Структура проекта

```
paganini/
├── main.py              # Точка входа
├── database/            # Модели и работа с БД
│   ├── engine.py
│   └── models.py
├── handlers/            # Обработчики команд Telegram
│   ├── common.py        # Регистрация, старт
│   ├── user.py          # Профиль, платежи
│   ├── reports.py       # Генерация отчетов
│   ├── admin.py         # Админ-панель
│   └── partners.py      # Реферальная программа
├── services/            # Бизнес-логика
│   ├── report_generator.py  # Парсинг отчетов WB
│   ├── auth_service.py
│   ├── payment.py
│   ├── manage_stores.py
│   └── refs.py
├── keyboards/           # Клавиатуры Telegram
├── filters/             # Фильтры сообщений
├── middlewares/         # Middleware
├── common/              # Общие константы
└── media/               # Медиа-файлы
```

## API Wildberries

Бот использует следующие API:

| API | Назначение |
|-----|------------|
| statistics-api | Детализация продаж |
| seller-analytics-api | Хранение, приёмка |
| advert-api | Рекламные расходы |
| content-api | Карточки товаров |

### Необходимые права токена WB

При создании токена в личном кабинете WB выберите:
- Контент
- Статистика
- Аналитика
- Продвижение
- Доступ: Чтение

## Деплой на Amvera

Проект готов к деплою на Amvera Cloud. Файл `amvera.yml` уже настроен.

```bash
# Установка Amvera CLI
pip install amvera

# Логин
amvera login

# Деплой
amvera push
```

## Лицензия

Проприетарная лицензия. Все права защищены.
