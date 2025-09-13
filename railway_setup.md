# 🚀 Развертывание бота на Railway

## 📋 Подготовка к деплою

### 1. Создание файлов для Railway

#### `Procfile`
```
worker: python bot.py
```

#### `runtime.txt`
```
python-3.11.0
```

#### `.env.example`
```
BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:password@host:port/database
```

### 2. Обновление кода для Railway

#### Изменения в `config.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Установите переменную окружения BOT_TOKEN")

# Для Railway используем PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')
```

#### Изменения в `database.py`:
```python
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

# Поддержка PostgreSQL для Railway
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

if DATABASE_URL.startswith('postgresql://'):
    # Конвертируем URL для asyncpg
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
```

### 3. Обновление requirements.txt
```
aiogram==3.2.0
aiosqlite==0.19.0
python-dotenv==1.0.0
sqlalchemy==2.0.23
asyncpg==0.29.0
```

## 🚀 Пошаговый деплой

### Шаг 1: Создание GitHub репозитория
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/bot_fm.git
git push -u origin main
```

### Шаг 2: Настройка Railway
1. Зайти на [railway.app](https://railway.app)
2. Войти через GitHub
3. Нажать "New Project"
4. Выбрать "Deploy from GitHub repo"
5. Выбрать репозиторий `bot_fm`

### Шаг 3: Настройка переменных окружения
В Railway Dashboard:
- `BOT_TOKEN` = ваш токен бота
- `DATABASE_URL` = автоматически создается Railway

### Шаг 4: Деплой
Railway автоматически:
- Установит зависимости
- Запустит бота
- Создаст базу данных

## 📊 Мониторинг

### Логи
- Railway Dashboard → Logs
- Реальное время
- История ошибок

### Метрики
- CPU использование
- Память
- Сеть

## 💰 Стоимость

### Бесплатный план:
- ✅ 500 часов в месяц
- ✅ 1GB RAM
- ✅ 1GB диск
- ✅ PostgreSQL база данных

### Для 24/7 работы:
- 💰 $5/месяц за дополнительные часы
- 💰 $5/месяц за базу данных

## 🔧 Альтернативы

### Если Railway не подходит:

#### 1. Render (750 часов бесплатно)
- Аналогичная настройка
- Медленный старт после сна

#### 2. Heroku (550-1000 часов бесплатно)
- Классический выбор
- Спит после 30 минут

#### 3. VPS (от $3-5/месяц)
- DigitalOcean, Vultr, Linode
- Полный контроль
- 24/7 работа

## 🎯 Рекомендация

**Railway** - лучший выбор для начала:
- Простота настройки
- Автоматический деплой
- Встроенная база данных
- Хорошая документация
- Надежная работа
