"""
Модуль для работы с базой данных SQLite
"""
import aiosqlite
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH


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
                    photo_file_id TEXT
                )
            """)
            
            # Создаем таблицу лайков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    FOREIGN KEY (from_user_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (to_user_id) REFERENCES users (telegram_id),
                    UNIQUE(from_user_id, to_user_id)
                )
            """)
            
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
