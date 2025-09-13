"""
Модуль для работы с базой данных SQLite
"""
import aiosqlite
import os
from typing import Optional, List, Dict, Any

# Путь к базе данных
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_database.db')


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Создаем таблицу пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    about TEXT NOT NULL,
                    photo_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем таблицу лайков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_user_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (to_user_id) REFERENCES users (telegram_id),
                    UNIQUE(from_user_id, to_user_id)
                )
            """)
            
            # Создаем индексы для улучшения производительности
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_branch ON users(branch)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_likes_from_user ON likes(from_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_likes_to_user ON likes(to_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_likes_pair ON likes(from_user_id, to_user_id)")
            
            # Включаем WAL режим для лучшей производительности
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=10000")
            await db.execute("PRAGMA temp_store=MEMORY")
            
            await db.commit()
    
    async def add_user(self, telegram_id: int, name: str, branch: str, 
                      job_title: str, about: str, photo_file_id: Optional[str] = None) -> bool:
        """Добавить или обновить пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO users 
                    (telegram_id, name, branch, job_title, about, photo_file_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (telegram_id, name, branch, job_title, about, photo_file_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            return False
    
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить пользователя по telegram_id"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_random_user(self, exclude_telegram_id: int, viewed_users: list = None) -> Optional[Dict[str, Any]]:
        """Получить случайного пользователя, исключая указанного и уже просмотренных"""
        if viewed_users is None:
            viewed_users = []
        
        # Добавляем текущего пользователя в список исключений
        exclude_list = [exclude_telegram_id] + viewed_users
        
        # Создаем плейсхолдеры для SQL запроса
        placeholders = ','.join(['?' for _ in exclude_list])
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"""
                SELECT * FROM users 
                WHERE telegram_id NOT IN ({placeholders})
                ORDER BY RANDOM() 
                LIMIT 1
            """, exclude_list)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def add_like(self, from_user_id: int, to_user_id: int) -> bool:
        """Добавить лайк"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO likes (from_user_id, to_user_id)
                    VALUES (?, ?)
                """, (from_user_id, to_user_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"Ошибка при добавлении лайка: {e}")
            return False
    
    async def check_match(self, user1_id: int, user2_id: int) -> bool:
        """Проверить, есть ли взаимный лайк между пользователями"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM likes 
                WHERE (from_user_id = ? AND to_user_id = ?) 
                OR (from_user_id = ? AND to_user_id = ?)
            """, (user1_id, user2_id, user2_id, user1_id))
            count = await cursor.fetchone()
            return count[0] >= 2
    
    async def get_user_username(self, telegram_id: int) -> Optional[str]:
        """Получить username пользователя (для уведомлений о совпадениях)"""
        # В реальном приложении нужно получать username через Telegram API
        # Здесь возвращаем telegram_id как заглушку
        return f"user_{telegram_id}"
    
    async def get_user_contact_info(self, telegram_id: int) -> Dict[str, Any]:
        """Получить полную контактную информацию пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT name, branch, job_title, about FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            user_data = await cursor.fetchone()
            return dict(user_data) if user_data else {}
    
    async def get_pending_likes(self, to_user_id: int) -> List[Dict[str, Any]]:
        """Получить список лайков, на которые пользователь еще не ответил"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT l.from_user_id, u.name, u.branch, u.job_title, u.about
                FROM likes l
                JOIN users u ON l.from_user_id = u.telegram_id
                WHERE l.to_user_id = ? 
                AND NOT EXISTS (
                    SELECT 1 FROM likes l2 
                    WHERE l2.from_user_id = ? AND l2.to_user_id = l.from_user_id
                )
            """, (to_user_id, to_user_id))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def delete_user(self, telegram_id: int) -> bool:
        """Удалить пользователя и все его лайки"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Удаляем лайки пользователя
                await db.execute("DELETE FROM likes WHERE from_user_id = ? OR to_user_id = ?", 
                               (telegram_id, telegram_id))
                # Удаляем пользователя
                await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
                await db.commit()
                return True
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {e}")
            return False
    
    async def get_users_count(self) -> int:
        """Получить количество пользователей в базе"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            count = await cursor.fetchone()
            return count[0] if count else 0
    
    async def get_users_by_ids(self, user_ids: list) -> List[Dict[str, Any]]:
        """Получить пользователей по списку ID"""
        if not user_ids:
            return []
        
        placeholders = ','.join(['?' for _ in user_ids])
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"""
                SELECT * FROM users 
                WHERE telegram_id IN ({placeholders})
                ORDER BY name
            """, user_ids)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def search_users_by_name(self, search_query: str, exclude_telegram_id: int = None) -> List[Dict[str, Any]]:
        """Поиск пользователей по имени (частичное совпадение)"""
        search_query_lower = search_query.lower().strip()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if exclude_telegram_id:
                cursor = await db.execute("""
                    SELECT * FROM users
                    WHERE telegram_id != ?
                    ORDER BY name
                """, (exclude_telegram_id,))
            else:
                cursor = await db.execute("""
                    SELECT * FROM users
                    ORDER BY name
                """)
            rows = await cursor.fetchall()
            
            # Фильтрация по регистру и частичному совпадению на уровне Python
            results = []
            for row in rows:
                name_lower = row['name'].lower()
                
                # Проверяем различные варианты поиска
                if (search_query_lower in name_lower or  # Частичное совпадение
                    any(word.startswith(search_query_lower) for word in name_lower.split()) or  # Начинается с поискового запроса
                    any(search_query_lower in word for word in name_lower.split())):  # Содержится в любом слове
                    results.append(dict(row))
            
            return results

    async def search_users_by_branch(self, search_query: str, exclude_telegram_id: int = None) -> List[Dict[str, Any]]:
        """Поиск пользователей по отрасли (частичное совпадение)"""
        search_query_lower = search_query.lower().strip()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if exclude_telegram_id:
                cursor = await db.execute("""
                    SELECT * FROM users
                    WHERE telegram_id != ? AND branch IS NOT NULL AND branch != ''
                    ORDER BY branch, name
                """, (exclude_telegram_id,))
            else:
                cursor = await db.execute("""
                    SELECT * FROM users
                    WHERE branch IS NOT NULL AND branch != ''
                    ORDER BY branch, name
                """)
            rows = await cursor.fetchall()
            
            # Фильтрация по регистру и частичному совпадению на уровне Python
            results = []
            for row in rows:
                branch_lower = row['branch'].lower()
                
                # Проверяем различные варианты поиска
                if (search_query_lower in branch_lower or  # Частичное совпадение
                    any(word.startswith(search_query_lower) for word in branch_lower.split()) or  # Начинается с поискового запроса
                    any(search_query_lower in word for word in branch_lower.split())):  # Содержится в любом слове
                    results.append(dict(row))
            
            return results

    async def get_branches_list(self, exclude_telegram_id: int = None) -> List[str]:
        """Получает список всех отраслей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if exclude_telegram_id:
                cursor = await db.execute("""
                    SELECT DISTINCT branch FROM users
                    WHERE telegram_id != ? AND branch IS NOT NULL AND branch != ''
                    ORDER BY branch
                """, (exclude_telegram_id,))
            else:
                cursor = await db.execute("""
                    SELECT DISTINCT branch FROM users
                    WHERE branch IS NOT NULL AND branch != ''
                    ORDER BY branch
                """)
            rows = await cursor.fetchall()
            return [row['branch'] for row in rows]

    async def search_users_by_keywords(self, keywords: str, exclude_telegram_id: int = None) -> List[Dict[str, Any]]:
        """Поиск пользователей по ключевым словам в имени, филиале, должности и интересах"""
        keywords_lower = keywords.lower().strip()
        if not keywords_lower:
            return []
        
        search_terms = [term.strip() for term in keywords_lower.split() if term.strip()]
        if not search_terms:
            return []
        
        # Используем FTS (Full Text Search) для более быстрого поиска
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Создаем временную таблицу FTS для поиска
            await db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS users_fts USING fts5(
                    name, branch, job_title, about,
                    content='users',
                    content_rowid='id'
                )
            """)
            
            # Заполняем FTS таблицу, если она пустая
            await db.execute("""
                INSERT OR IGNORE INTO users_fts(rowid, name, branch, job_title, about)
                SELECT id, name, branch, job_title, about FROM users
            """)
            
            # Выполняем поиск через FTS
            search_query = " ".join([f'"{term}"' for term in search_terms])
            exclude_condition = "AND u.telegram_id != ?" if exclude_telegram_id else ""
            params = [exclude_telegram_id] if exclude_telegram_id else []
            
            cursor = await db.execute(f"""
                SELECT u.* FROM users u
                JOIN users_fts fts ON u.id = fts.rowid
                WHERE users_fts MATCH ? {exclude_condition}
                ORDER BY rank
                LIMIT 50
            """, [search_query] + params)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
