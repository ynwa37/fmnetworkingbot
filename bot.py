"""
Telegram бот для знакомств
"""
import asyncio
import logging
from functools import lru_cache
from typing import Dict, Any, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os
from config import MESSAGES

# Получаем токен из переменных окружения или config.py
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    try:
        from config import BOT_TOKEN
    except ImportError:
        raise ValueError("BOT_TOKEN не найден!")

# Создаем объект бота
bot = Bot(token=BOT_TOKEN)
# BOT_ID будет получен асинхронно в main()
BOT_ID = None

from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация диспетчера (бот уже создан выше)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация базы данных
db = Database()


class ProfileStates(StatesGroup):
    """Состояния для заполнения анкеты"""
    waiting_for_name = State()
    waiting_for_branch = State()
    waiting_for_job_title = State()
    waiting_for_about = State()
    waiting_for_photo = State()


class SearchStates(StatesGroup):
    """Состояния для поиска"""
    viewing_profile = State()
    waiting_for_search_query = State()
    waiting_for_keywords = State()


# Временное хранилище для текущего просматриваемого профиля
current_viewing = {}

# Хранилище просмотренных пользователей для каждого пользователя
viewed_users = {}

# Кэш для часто используемых данных
user_cache = {}  # {telegram_id: user_data}
cache_ttl = 300  # 5 минут

# Очищаем кэш при запуске
user_cache.clear()

def get_cached_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Получить пользователя из кэша"""
    return user_cache.get(telegram_id)

def set_cached_user(telegram_id: int, user_data: Dict[str, Any]):
    """Сохранить пользователя в кэш"""
    user_cache[telegram_id] = user_data

def clear_cache():
    """Очистить кэш"""
    user_cache.clear()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего действия"""
    await cancel_profile_creation(message, state)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    # Проверяем, есть ли уже анкета у пользователя
    user = await db.get_user(message.from_user.id)
    
    if user:
        # Показываем главное меню с улучшенным приветствием
        await message.answer(
            "🎉 **Добро пожаловать в Формулу молодежи!**\n\n"
            "Здесь вы можете знакомиться с другими участниками форума и находить интересные связи для общения.\n\n"
            "**🔍 Поиск людей:**\n"
            "• Случайный поиск\n"
            "• Поиск по ключевым словам\n\n"
            "**👤 Управление профилем:**\n"
            "• Просмотр и редактирование\n"
            "• История просмотров\n"
            "• Статистика активности\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        # Показываем приветствие и начинаем заполнение анкеты
        await message.answer(
            "🎉 **Добро пожаловать в Формулу молодежи!**\n\n"
            "Для начала работы необходимо создать профиль. Это займет всего несколько минут!\n\n"
            "Нажмите кнопку ниже, чтобы начать:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )


@dp.callback_query(F.data == "create_profile")
async def start_profile_creation(callback: CallbackQuery, state: FSMContext):
    """Начинает создание профиля"""
    await callback.message.edit_text(
        "📝 **Создание профиля**\n\n"
        "Давайте создадим ваш профиль для знакомств на форуме!\n\n"
        "**Шаг 1/5:** Как вас зовут?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
        ])
    )
    await callback.answer()
    await state.set_state(ProfileStates.waiting_for_name)

@dp.message(StateFilter(ProfileStates.waiting_for_name))
async def process_name(message: types.Message, state: FSMContext):
    """Обработка ввода имени"""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(name=name)
    
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    if is_edit:
        # Если редактирование - сохраняем только имя, остальное обработается отдельно
        await state.update_data(name=message.text)
        await message.answer(
            "✅ **Имя обновлено!**\n\n"
            "**Шаг 2/5:** В каком филиале вы работаете?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
            ])
        )
        await state.set_state(ProfileStates.waiting_for_branch)


@dp.message(StateFilter(ProfileStates.waiting_for_branch))
async def process_branch(message: types.Message, state: FSMContext):
    """Обработка ввода филиала"""
    branch = message.text.strip()
    if len(branch) < 2:
        await message.answer("❌ Название филиала должно содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(branch=branch)
    
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    if is_edit:
        # Если редактирование - сохраняем только филиал, остальное обработается отдельно
        await state.update_data(branch=message.text)
        await message.answer(
            "✅ **Филиал обновлен!**\n\n"
            "**Шаг 3/5:** Какова ваша должность?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
            ])
        )
        await state.set_state(ProfileStates.waiting_for_job_title)


@dp.message(StateFilter(ProfileStates.waiting_for_job_title))
async def process_job_title(message: types.Message, state: FSMContext):
    """Обработка ввода должности"""
    job_title = message.text.strip()
    if len(job_title) < 2:
        await message.answer("❌ Должность должна содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(job_title=job_title)
    
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    if is_edit:
        # Если редактирование - сохраняем только должность, остальное обработается отдельно
        await state.update_data(job_title=message.text)
        await message.answer(
            "✅ **Должность обновлена!**\n\n"
            "**Шаг 4/5:** Расскажите о ваших интересах, навыках и целях:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
            ])
        )
        await state.set_state(ProfileStates.waiting_for_about)


@dp.message(StateFilter(ProfileStates.waiting_for_about))
async def process_about(message: types.Message, state: FSMContext):
    """Обработка ввода информации о себе"""
    about = message.text.strip()
    if len(about) < 10:
        await message.answer("❌ Расскажите о себе подробнее (минимум 10 символов). Попробуйте еще раз:")
        return
    
    await state.update_data(about=about)
    
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    if is_edit:
        # Если редактирование - сохраняем только текст, фото обработается отдельно
        await state.update_data(about=message.text)
        await message.answer(
            "✅ **Описание обновлено!**\n\n"
            "Хотите добавить фото к анкете?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
                [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
            ])
        )
        await state.set_state(ProfileStates.waiting_for_photo)
    else:
        # Если создание - продолжаем процесс
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
        ])
        
        await message.answer(
            "✅ **Интересы сохранены!**\n\n"
            "**Шаг 5/5:** Хотите добавить фото к анкете?",
            reply_markup=keyboard
        )
        await state.set_state(ProfileStates.waiting_for_photo)


@dp.callback_query(F.data == "add_photo")
async def process_add_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора добавления фото"""
    await callback.message.edit_text("📷 Отправьте ваше фото:")
    await state.set_state(ProfileStates.waiting_for_photo)


@dp.callback_query(F.data == "skip_photo")
async def process_skip_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска фото"""
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    await save_profile(callback.message, state, photo_file_id=None, is_edit=is_edit, remove_photo=True)
    await callback.answer()


@dp.message(StateFilter(ProfileStates.waiting_for_photo), F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработка загрузки фото"""
    photo_file_id = message.photo[-1].file_id
    
    # Проверяем, редактируется ли профиль
    data = await state.get_data()
    is_edit = data.get('is_edit', False)
    
    await save_profile(message, state, photo_file_id, is_edit=is_edit)


@dp.message(StateFilter(ProfileStates.waiting_for_photo))
async def process_photo_invalid(message: types.Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания фото"""
    await message.answer("❌ Пожалуйста, отправьте фото или нажмите 'Пропустить'")


async def save_profile(message: types.Message, state: FSMContext, photo_file_id: str = None, is_edit: bool = False, remove_photo: bool = False):
    """Сохранение профиля в базу данных"""
    data = await state.get_data()
    
    # Отладочная информация
    logger.info(f"💾 save_profile: photo_file_id = {photo_file_id}")
    logger.info(f"💾 is_edit = {is_edit}")
    logger.info(f"💾 data keys: {list(data.keys())}")
    
    # Проверяем наличие обязательных полей
    required_fields = ['name', 'branch', 'job_title', 'about']
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    
    if missing_fields:
        logger.error(f"❌ Отсутствуют обязательные поля: {missing_fields}")
        await message.answer(
            f"❌ **Ошибка:** Не все поля заполнены!\n\n"
            f"Отсутствуют: {', '.join(missing_fields)}\n\n"
            f"Пожалуйста, заполните анкету заново.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        return
    
    if is_edit:
        # Обновляем существующий профиль
        # Определяем final_photo_file_id
        if remove_photo:
            # Явно удаляем фото
            final_photo_file_id = None
        elif photo_file_id is not None:
            # Передано новое фото
            final_photo_file_id = photo_file_id
        else:
            # Используем существующее фото из FSM
            final_photo_file_id = data.get('photo_file_id')
        
        logger.info(f"🔄 Обновление профиля: final_photo_file_id = {final_photo_file_id}")
        logger.info(f"🔄 photo_file_id из параметра = {photo_file_id}")
        logger.info(f"🔄 photo_file_id из FSM = {data.get('photo_file_id')}")
        logger.info(f"🔄 remove_photo = {remove_photo}")
        
        success = await db.update_user(
            telegram_id=message.from_user.id,
            name=data['name'],
            branch=data['branch'],
            job_title=data['job_title'],
            about=data['about'],
            photo_file_id=final_photo_file_id,
            update_photo=True
        )
        
        logger.info(f"🔄 Результат обновления: success = {success}")
        
        if success:
            await state.clear()
            # Получаем обновленные данные профиля
            updated_user_data = await db.get_user(message.from_user.id)
            if updated_user_data:
                await message.answer(
                    "✅ **Профиль успешно обновлен!**\n\n"
                    "Изменения сохранены.",
                    reply_markup=get_main_menu_keyboard()
                )
                # Показываем обновленную карточку профиля
                await show_profile_card(message, updated_user_data, is_own_profile=True)
            else:
                await message.answer("❌ Произошла ошибка при получении обновленного профиля.")
        else:
            await message.answer("❌ Произошла ошибка при обновлении профиля. Попробуйте еще раз.")
    else:
        # Создаем новый профиль
        success = await db.add_user(
            telegram_id=message.from_user.id,
            name=data['name'],
            branch=data['branch'],
            job_title=data['job_title'],
            about=data['about'],
            photo_file_id=photo_file_id
        )
        
        if success:
            await state.clear()
            await message.answer(
                "🎉 **Профиль успешно создан!**\n\n"
                "Теперь вы можете знакомиться с другими участниками форума.",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await message.answer("❌ Произошла ошибка при сохранении анкеты. Попробуйте еще раз.")


def get_main_menu_keyboard():
    """Создание главного меню с улучшенным дизайном"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        # Группа поиска - универсальный поиск
        [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
        [InlineKeyboardButton(text="🔎 Поиск по ключевым словам", callback_data="search_by_keywords")],
        
        # Разделитель
        [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━━", callback_data="separator")],
        
        # Управление профилем
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
        [InlineKeyboardButton(text="👀 Просмотренные", callback_data="viewed_list")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")],
        
        # Разделитель
        [InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━━", callback_data="separator")],
        
        # Системные функции
        [InlineKeyboardButton(text="🔄 Сбросить анкету", callback_data="reset_profile")]
    ])
    return keyboard


async def check_profile_exists(user_id: int) -> bool:
    """Проверяет, существует ли анкета у пользователя"""
    user = await db.get_user(user_id)
    return user is not None

async def cancel_profile_creation(message: types.Message, state: FSMContext):
    """Отмена создания анкеты"""
    await state.clear()
    await message.answer(
        "❌ Создание анкеты отменено.\n\n"
        "Используйте команду /start для создания анкеты.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать анкету", callback_data="main_menu")]
        ])
    )

async def show_main_menu(message: types.Message):
    """Показ главного меню"""
    await message.answer("🏠 Главное меню", reply_markup=get_main_menu_keyboard())


@dp.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    """Начало поиска"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли анкета у пользователя
    if not await check_profile_exists(user_id):
        await callback.message.edit_text(
            "❌ **Сначала создайте профиль!**\n\n"
            "Для поиска людей необходимо заполнить анкету.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли другие пользователи
    users_count = await db.get_users_count()
    if users_count < 2:
        await callback.message.edit_text(
            "😔 **Пока нет доступных профилей**\n\n"
            "Попробуйте позже или создайте тестовые профили.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="search")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем список уже просмотренных пользователей
    user_viewed = viewed_users.get(user_id, [])
    
    # Получаем случайного пользователя, исключая просмотренных
    random_user = await db.get_random_user(user_id, user_viewed)
    if not random_user:
        # Если все пользователи просмотрены, сбрасываем список
        viewed_users[user_id] = []
        await callback.message.edit_text(
            "🎉 **Все профили просмотрены!**\n\n"
            "Список обновлен, попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Начать заново", callback_data="search")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Добавляем текущего пользователя в список просмотренных
    viewed_users[user_id] = user_viewed + [random_user['telegram_id']]
    
    # Сохраняем текущего просматриваемого пользователя
    current_viewing[user_id] = random_user
    
    # Показываем карточку
    await show_profile_card(callback.message, random_user)
    await callback.answer()


def get_profile_card_keyboard():
    """Создание клавиатуры для карточки профиля"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Познакомиться", callback_data="like")],
        [InlineKeyboardButton(text="➡️ Дальше", callback_data="next")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    return keyboard


def format_profile_card(user_data: dict):
    """Форматирует карточку профиля с улучшенным дизайном"""
    card = f"👤 **{user_data['name']}**\n\n"
    
    if user_data.get('branch'):
        card += f"🏢 **Филиал:** {user_data['branch']}\n"
    
    if user_data.get('job_title'):
        card += f"💼 **Должность:** {user_data['job_title']}\n"
    
    if user_data.get('about'):
        card += f"📝 **О себе:** {user_data['about']}\n"
    
    card += "\n" + "─" * 30 + "\n"
    card += "💡 Нажмите '🤝 Познакомиться' для обмена контактами"
    
    return card

def format_contact_info(user_data: dict, telegram_id: int) -> str:
    """Форматирование контактной информации для совпадений"""
    text = f"👤 **{user_data['name']}**\n"
    text += f"🏢 **Филиал:** {user_data['branch']}\n"
    text += f"💼 **Должность:** {user_data['job_title']}\n"
    text += f"🆔 **ID для связи:** `{telegram_id}`\n"
    
    if user_data.get('about'):
        # Показываем только первые 100 символов описания
        about = user_data['about'][:100]
        if len(user_data['about']) > 100:
            about += "..."
        text += f"📝 **О себе:** {about}\n"
    
    return text

def get_contact_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Создание клавиатуры с контактами для совпадений"""
    # Проверяем, является ли ID реальным Telegram ID (обычно больше 100000000)
    # и не является ли тестовым ID
    if telegram_id > 100000000 and telegram_id not in [123456789, 4001, 5001, 6001, 7001, 8001]:
        try:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={telegram_id}")],
                [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        except Exception:
            # Если не удалось создать кнопку с URL, используем безопасную версию
            pass
    
    # Для тестовых ID или в случае ошибки показываем только навигационные кнопки
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def get_response_keyboard(from_user_id: int) -> InlineKeyboardMarkup:
    """Создание клавиатуры с кнопками ответа на запрос знакомства"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Познакомиться", callback_data=f"respond_like_{from_user_id}")],
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data=f"skip_like_{from_user_id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

async def show_profile_card(message: types.Message, user_data: dict, is_own_profile: bool = False):
    """Показ карточки профиля"""
    text = format_profile_card(user_data)
    
    # Отладочная информация
    logger.info(f"🔍 show_profile_card: photo_file_id = {user_data.get('photo_file_id')}")
    logger.info(f"🔍 user_data keys: {list(user_data.keys())}")
    logger.info(f"🔍 is_own_profile = {is_own_profile}")
    
    # Выбираем клавиатуру в зависимости от того, чей это профиль
    if is_own_profile:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    else:
        keyboard = get_profile_card_keyboard()
    
    if user_data.get('photo_file_id'):
        logger.info("📸 Отправляем фото с подписью")
        await message.answer_photo(
            photo=user_data['photo_file_id'],
            caption=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        logger.info("📝 Отправляем только текст")
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def edit_profile_card(callback: CallbackQuery, user_data: dict):
    """Редактирование карточки профиля"""
    text = format_profile_card(user_data)
    
    if user_data.get('photo_file_id'):
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=user_data['photo_file_id'],
                    caption=text,
                    parse_mode="Markdown"
                ),
                reply_markup=get_profile_card_keyboard()
            )
        except Exception:
            # Если не получается отредактировать медиа, отправляем новое сообщение
            await callback.message.answer_photo(
                photo=user_data['photo_file_id'],
                caption=text,
                parse_mode="Markdown",
                reply_markup=get_profile_card_keyboard()
            )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_profile_card_keyboard()
        )


@dp.callback_query(F.data == "like")
async def process_like(callback: CallbackQuery, state: FSMContext):
    """Обработка лайка"""
    user_id = callback.from_user.id
    viewed_user = current_viewing.get(user_id)
    
    if not viewed_user:
        await callback.message.edit_text("❌ Профиль не найден. Попробуйте поиск заново.")
        await callback.answer()
        return
    
    # Добавляем интерес к знакомству
    await db.add_like(user_id, viewed_user['telegram_id'])
    
    # Проверяем на взаимный интерес
    is_match = await db.check_match(user_id, viewed_user['telegram_id'])
    
    if is_match:
        # Получаем полную контактную информацию
        contact_info = await db.get_user_contact_info(viewed_user['telegram_id'])
        
        try:
            await callback.message.edit_text(
                f"🎉 **Взаимный интерес!**\n\n"
                f"Вы и {viewed_user['name']} хотите познакомиться!\n\n"
                f"💬 **Контакты для связи:**\n"
                f"{format_contact_info(contact_info, viewed_user['telegram_id'])}\n"
                f"Теперь вы можете связаться и общаться!",
                reply_markup=get_contact_keyboard(viewed_user['telegram_id'])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            await callback.message.answer(
                f"🎉 **Взаимный интерес!**\n\n"
                f"Вы и {viewed_user['name']} хотите познакомиться!\n\n"
                f"💬 **Контакты для связи:**\n"
                f"{format_contact_info(contact_info, viewed_user['telegram_id'])}\n"
                f"Теперь вы можете связаться и общаться!",
                reply_markup=get_contact_keyboard(viewed_user['telegram_id'])
            )
        
        # Уведомляем другого пользователя о взаимном интересе
        other_contact_info = await db.get_user_contact_info(user_id)
        try:
            await bot.send_message(
                viewed_user['telegram_id'],
                f"🎉 **Взаимный интерес!**\n\n"
                f"Вы и {other_contact_info['name']} хотите познакомиться!\n\n"
                f"💬 **Контакты для связи:**\n"
                f"{format_contact_info(other_contact_info, user_id)}\n"
                f"Теперь вы можете связаться и общаться!",
                reply_markup=get_contact_keyboard(user_id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    else:
        # Отправляем уведомление другому пользователю о новом интересе
        try:
            await send_like_notification_with_buttons(viewed_user['telegram_id'], user_id)
            logger.info(f"Уведомление о лайке отправлено пользователю {viewed_user['telegram_id']}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о лайке: {e}")
        
        try:
            await callback.message.edit_text(
                f"✅ **Интерес отправлен!**\n\n"
                f"Вы выразили желание познакомиться с {viewed_user['name']}!\n\n"
                f"Если {viewed_user['name']} тоже захочет познакомиться, вы получите уведомление о взаимном интересе.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            await callback.message.answer(
                f"✅ **Интерес отправлен!**\n\n"
                f"Вы выразили желание познакомиться с {viewed_user['name']}!\n\n"
                f"Если {viewed_user['name']} тоже захочет познакомиться, вы получите уведомление о взаимном интересе.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
    
    # Добавляем в список просмотренных
    if user_id not in viewed_users:
        viewed_users[user_id] = []
    if viewed_user['telegram_id'] not in viewed_users[user_id]:
        viewed_users[user_id].append(viewed_user['telegram_id'])
        logger.info(f"Добавлен в просмотренные: {viewed_user['name']} (ID: {viewed_user['telegram_id']})")
    else:
        logger.info(f"Уже в просмотренных: {viewed_user['name']} (ID: {viewed_user['telegram_id']})")
    
    # Удаляем из текущего просмотра
    if user_id in current_viewing:
        del current_viewing[user_id]
    
    await callback.answer()


@dp.callback_query(F.data == "next")
async def process_next(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Дальше'"""
    user_id = callback.from_user.id
    
    # Добавляем текущего пользователя в список просмотренных
    if user_id in current_viewing:
        viewed_user = current_viewing[user_id]
        if user_id not in viewed_users:
            viewed_users[user_id] = []
        if viewed_user['telegram_id'] not in viewed_users[user_id]:
            viewed_users[user_id].append(viewed_user['telegram_id'])
            logger.info(f"Добавлен в просмотренные (Дальше): {viewed_user['name']} (ID: {viewed_user['telegram_id']})")
        else:
            logger.info(f"Уже в просмотренных (Дальше): {viewed_user['name']} (ID: {viewed_user['telegram_id']})")
        del current_viewing[user_id]
    
    # Получаем список уже просмотренных пользователей
    user_viewed = viewed_users.get(user_id, [])
    
    # Ищем следующего пользователя, исключая просмотренных
    random_user = await db.get_random_user(user_id, user_viewed)
    if not random_user:
        # Если все пользователи просмотрены, сбрасываем список
        viewed_users[user_id] = []
        await callback.message.edit_text(
            "🎉 **Все профили просмотрены!**\n\n"
            "Список обновлен, попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Начать заново", callback_data="search")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Добавляем нового пользователя в список просмотренных
    viewed_users[user_id] = user_viewed + [random_user['telegram_id']]
    
    # Сохраняем нового пользователя
    current_viewing[user_id] = random_user
    
    # Показываем новую карточку
    await show_profile_card(callback.message, random_user)
    await callback.answer()


@dp.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    if user_id in current_viewing:
        del current_viewing[user_id]
    
    # НЕ сбрасываем список просмотренных пользователей - он должен сохраняться
    # if user_id in viewed_users:
    #     del viewed_users[user_id]
    
    try:
        # Пытаемся отредактировать сообщение
        await callback.message.edit_text(
            "🏠 **Главное меню**\n\n"
            "**🔍 Поиск людей:**\n"
            "• Случайный поиск\n"
            "• Поиск по ключевым словам\n\n"
            "**👤 Управление профилем:**\n"
            "• Просмотр и редактирование\n"
            "• История просмотров\n"
            "• Статистика активности\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        # Если не получается отредактировать (например, сообщение только с фото), отправляем новое
        await callback.message.answer(
            "🏠 **Главное меню**\n\n"
            "**🔍 Поиск людей:**\n"
            "• Случайный поиск\n"
            "• Поиск по ключевым словам\n\n"
            "**👤 Управление профилем:**\n"
            "• Просмотр и редактирование\n"
            "• История просмотров\n"
            "• Статистика активности\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    await callback.answer()


@dp.callback_query(F.data == "search_by_keywords")
async def start_search_by_keywords(callback: CallbackQuery, state: FSMContext):
    """Начало поиска по ключевым словам"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли анкета у пользователя
    if not await check_profile_exists(user_id):
        await callback.message.edit_text(
            "❌ **Сначала создайте профиль!**\n\n"
            "Для поиска людей необходимо заполнить анкету.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🔎 **Поиск по ключевым словам**\n\n"
        "Введите ключевые слова для поиска. Поиск будет выполняться по:\n"
        "• Имени\n"
        "• Филиалу\n"
        "• Должности\n"
        "• Интересам\n\n"
        "💡 **Примеры:**\n"
        "• 'Анна IT' - найдет Анну из IT\n"
        "• 'маркетинг менеджер' - найдет менеджеров по маркетингу\n"
        "• 'программист Python' - найдет Python-разработчиков\n"
        "• 'дизайн творчество' - найдет дизайнеров",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
        ])
    )
    await state.set_state(SearchStates.waiting_for_keywords)
    await callback.answer()




@dp.message(StateFilter(SearchStates.waiting_for_keywords))
async def process_keywords_search(message: types.Message, state: FSMContext):
    """Обработка поиска по ключевым словам"""
    keywords = message.text.strip()
    
    if len(keywords) < 2:
        await message.answer(
            "❌ **Поисковый запрос слишком короткий!**\n\n"
            "Введите минимум 2 символа для поиска:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
            ])
        )
        return
    
    # Ищем пользователей по ключевым словам
    search_results = await db.search_users_by_keywords(keywords, message.from_user.id)
    logger.info(f"Поиск по ключевым словам '{keywords}': найдено {len(search_results)} результатов")
    
    if not search_results:
        await message.answer(
            f"😔 **По ключевым словам '{keywords}' ничего не найдено**\n\n"
            "Попробуйте:\n"
            "• Другие ключевые слова\n"
            "• Более общие термины\n"
            "• Меньше слов в запросе",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Попробовать снова", callback_data="search_by_keywords")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await state.clear()
        return
    
    # Показываем результаты поиска
    if len(search_results) == 1:
        # Если найден один результат, показываем его карточку
        user_data = search_results[0]
        current_viewing[message.from_user.id] = user_data
        await show_profile_card(message, user_data)
        await state.clear()
    else:
        # Если найдено несколько результатов, показываем список
        text = f"🔎 **Найдено {len(search_results)} результатов по запросу '{keywords}':**\n\n"
        
        for i, user in enumerate(search_results[:10], 1):  # Показываем максимум 10 результатов
            text += f"{i}. **{user['name']}**\n"
            if user.get('branch'):
                text += f"   🏢 {user['branch']}"
            if user.get('job_title'):
                text += f" | 💼 {user['job_title']}"
            text += "\n\n"
        
        if len(search_results) > 10:
            text += f"... и еще {len(search_results) - 10} результатов\n\n"
        
        text += "💡 **Выберите человека из списка или уточните поиск**"
        
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Уточнить поиск", callback_data="search_by_keywords")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await state.clear()


@dp.callback_query(F.data.startswith("respond_like_"))
async def respond_to_like(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на лайк - познакомиться"""
    try:
        user_id = callback.from_user.id
        from_user_id = int(callback.data.split("_")[2])
        
        logger.info(f"Пользователь {user_id} отвечает на лайк от {from_user_id}")
        
        # Добавляем лайк в ответ
        await db.add_like(user_id, from_user_id)
        
        # Проверяем, есть ли теперь взаимный лайк
        is_match = await db.check_match(user_id, from_user_id)
        
        if is_match:
            # Получаем контактную информацию
            contact_info = await db.get_user_contact_info(from_user_id)
            
            try:
                await callback.message.edit_text(
                    f"🎉 **Взаимный интерес!**\n\n"
                    f"Вы и {contact_info['name']} хотите познакомиться!\n\n"
                    f"💬 **Контакты для связи:**\n"
                    f"{format_contact_info(contact_info, from_user_id)}\n"
                    f"Теперь вы можете связаться и общаться!",
                    reply_markup=get_contact_keyboard(from_user_id)
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                await callback.message.answer(
                    f"🎉 **Взаимный интерес!**\n\n"
                    f"Вы и {contact_info['name']} хотите познакомиться!\n\n"
                    f"💬 **Контакты для связи:**\n"
                    f"{format_contact_info(contact_info, from_user_id)}\n"
                    f"Теперь вы можете связаться и общаться!",
                    reply_markup=get_contact_keyboard(from_user_id)
                )
            
            # Уведомляем другого пользователя о совпадении (только если это реальный пользователь)
            if from_user_id != user_id and from_user_id > 100000000 and from_user_id not in [123456789, 4001, 5001, 6001, 7001, 8001]:
                other_contact_info = await db.get_user_contact_info(user_id)
                try:
                    await bot.send_message(
                        from_user_id,
                        f"🎉 **Взаимный интерес!**\n\n"
                        f"Вы и {other_contact_info['name']} хотите познакомиться!\n\n"
                        f"💬 **Контакты для связи:**\n"
                        f"{format_contact_info(other_contact_info, user_id)}\n"
                        f"Теперь вы можете связаться и общаться!",
                        reply_markup=get_contact_keyboard(user_id)
                    )
                    logger.info(f"Уведомление о совпадении отправлено пользователю {from_user_id}")
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {from_user_id}: {e}")
        else:
            try:
                await callback.message.edit_text(
                    f"✅ **Интерес отправлен!**\n\n"
                    f"Вы выразили желание познакомиться с пользователем!\n\n"
                    f"Если он тоже захочет познакомиться, вы получите уведомление о взаимном интересе.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                await callback.message.answer(
                    f"✅ **Интерес отправлен!**\n\n"
                    f"Вы выразили желание познакомиться с пользователем!\n\n"
                    f"Если он тоже захочет познакомиться, вы получите уведомление о взаимном интересе.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Найти еще", callback_data="search")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в respond_to_like: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)

@dp.callback_query(F.data.startswith("skip_like_"))
async def skip_like(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска лайка"""
    from_user_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_text(
        f"➡️ **Запрос пропущен**\n\n"
        f"Вы пропустили этот запрос на знакомство.\n\n"
        f"Можете продолжить поиск других людей!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    
    await callback.answer()

@dp.callback_query(F.data == "viewed_list")
async def show_viewed_list(callback: CallbackQuery, state: FSMContext):
    """Показ списка просмотренных пользователей"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли анкета у пользователя
    if not await check_profile_exists(user_id):
        await callback.message.edit_text(
            "❌ **Сначала создайте профиль!**\n\n"
            "Для просмотра списка необходимо заполнить анкету.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )
        await callback.answer()
        return
    
    user_viewed = viewed_users.get(user_id, [])
    logger.info(f"Просмотренные пользователи для {user_id}: {user_viewed}")
    
    if not user_viewed:
        await callback.message.edit_text(
            "👀 **Просмотренные профили**\n\n"
            "Вы еще никого не просматривали.\n\n"
            "Нажмите '🔍 Найти людей' чтобы начать поиск!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем информацию о просмотренных пользователях
    viewed_users_info = await db.get_users_by_ids(user_viewed)
    
    if not viewed_users_info:
        await callback.message.edit_text("❌ Ошибка при загрузке списка просмотренных.")
        await callback.answer()
        return
    
    # Формируем список
    text = f"👀 **Просмотренные профили** ({len(viewed_users_info)}):\n\n"
    
    for i, user in enumerate(viewed_users_info, 1):
        text += f"{i}. **{user['name']}**\n"
        if user.get('branch'):
            text += f"   🏢 {user['branch']}"
        if user.get('job_title'):
            text += f" | 💼 {user['job_title']}"
        text += "\n"
        if user.get('about'):
            text += f"   📝 {user['about'][:50]}...\n"
        text += "\n"
    
    # Добавляем кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Очистить список", callback_data="clear_viewed")],
        [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "clear_viewed")
async def clear_viewed_list(callback: CallbackQuery, state: FSMContext):
    """Очистка списка просмотренных пользователей"""
    user_id = callback.from_user.id
    
    # Очищаем список просмотренных
    if user_id in viewed_users:
        del viewed_users[user_id]
    
    await callback.message.edit_text(
        "✅ **Список просмотренных профилей очищен!**\n\n"
        "Теперь при поиске будут показаны все доступные профили.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery, state: FSMContext):
    """Показ профиля пользователя"""
    user_id = callback.from_user.id
    
    # Проверяем кэш
    user = get_cached_user(user_id)
    if not user:
        user = await db.get_user(user_id)
        if user:
            set_cached_user(user_id, user)
    
    if not user:
        await callback.message.edit_text(
            "❌ **Профиль не найден!**\n\n"
            "Используйте кнопку ниже для создания профиля.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    text = f"👤 **Ваш профиль**\n\n"
    text += f"**Имя:** {user['name']}\n"
    if user.get('branch'):
        text += f"**Филиал:** {user['branch']}\n"
    if user.get('job_title'):
        text += f"**Должность:** {user['job_title']}\n"
    if user.get('about'):
        text += f"**О себе:** {user['about']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    try:
        if user.get('photo_file_id'):
            await callback.message.answer_photo(
                photo=user['photo_file_id'],
                caption=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка при показе профиля: {e}")
        await callback.message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    await callback.answer()


@dp.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    """Редактирование профиля"""
    # Используем try-except для обработки сообщений с фото
    try:
        await callback.message.edit_text(
            "✏️ **Редактирование профиля**\n\n"
            "Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🏢 Филиал", callback_data="edit_branch")],
                [InlineKeyboardButton(text="💼 Должность", callback_data="edit_job_title")],
                [InlineKeyboardButton(text="📝 О себе", callback_data="edit_about")],
                [InlineKeyboardButton(text="📷 Фото", callback_data="edit_photo")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
    except Exception:
        # Если не удалось отредактировать (сообщение с фото), отправляем новое
        await callback.message.answer(
            "✏️ **Редактирование профиля**\n\n"
            "Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🏢 Филиал", callback_data="edit_branch")],
                [InlineKeyboardButton(text="💼 Должность", callback_data="edit_job_title")],
                [InlineKeyboardButton(text="📝 О себе", callback_data="edit_about")],
                [InlineKeyboardButton(text="📷 Фото", callback_data="edit_photo")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
    
    await callback.answer()

# Обработчики редактирования полей профиля
@dp.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    """Редактирование имени"""
    # Получаем текущие данные профиля
    user_data = await db.get_user(callback.from_user.id)
    if user_data:
        await state.update_data(
            name=user_data['name'],
            branch=user_data['branch'],
            job_title=user_data['job_title'],
            about=user_data['about'],
            photo_file_id=user_data.get('photo_file_id'),  # Включаем текущее фото
            is_edit=True
        )
    
    await state.set_state(ProfileStates.waiting_for_name)
    await callback.message.edit_text(
        "✏️ **Редактирование имени**\n\n"
        "Введите новое имя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "edit_branch")
async def edit_branch(callback: CallbackQuery, state: FSMContext):
    """Редактирование филиала"""
    # Получаем текущие данные профиля
    user_data = await db.get_user(callback.from_user.id)
    if user_data:
        await state.update_data(
            name=user_data['name'],
            branch=user_data['branch'],
            job_title=user_data['job_title'],
            about=user_data['about'],
            photo_file_id=user_data.get('photo_file_id'),  # Включаем текущее фото
            is_edit=True
        )
    
    await state.set_state(ProfileStates.waiting_for_branch)
    await callback.message.edit_text(
        "✏️ **Редактирование филиала**\n\n"
        "Введите новый филиал:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "edit_job_title")
async def edit_job_title(callback: CallbackQuery, state: FSMContext):
    """Редактирование должности"""
    # Получаем текущие данные профиля
    user_data = await db.get_user(callback.from_user.id)
    if user_data:
        await state.update_data(
            name=user_data['name'],
            branch=user_data['branch'],
            job_title=user_data['job_title'],
            about=user_data['about'],
            photo_file_id=user_data.get('photo_file_id'),  # Включаем текущее фото
            is_edit=True
        )
    
    await state.set_state(ProfileStates.waiting_for_job_title)
    await callback.message.edit_text(
        "✏️ **Редактирование должности**\n\n"
        "Введите новую должность:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "edit_about")
async def edit_about(callback: CallbackQuery, state: FSMContext):
    """Редактирование информации о себе"""
    # Получаем текущие данные профиля
    user_data = await db.get_user(callback.from_user.id)
    if user_data:
        await state.update_data(
            name=user_data['name'],
            branch=user_data['branch'],
            job_title=user_data['job_title'],
            about=user_data['about'],
            photo_file_id=user_data.get('photo_file_id'),  # Включаем текущее фото
            is_edit=True
        )
    
    await state.set_state(ProfileStates.waiting_for_about)
    await callback.message.edit_text(
        "✏️ **Редактирование информации о себе**\n\n"
        "Расскажите о себе, своих интересах и целях:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    """Редактирование фото"""
    # Получаем текущие данные профиля
    user_data = await db.get_user(callback.from_user.id)
    if user_data:
        await state.update_data(
            name=user_data['name'],
            branch=user_data['branch'],
            job_title=user_data['job_title'],
            about=user_data['about'],
            photo_file_id=user_data.get('photo_file_id'),  # Включаем текущее фото
            is_edit=True
        )
    
    await state.set_state(ProfileStates.waiting_for_photo)
    await callback.message.edit_text(
        "✏️ **Редактирование фото**\n\n"
        "Отправьте новое фото или нажмите 'Пропустить', чтобы удалить текущее:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "separator")
async def separator_handler(callback: CallbackQuery):
    """Обработчик для разделителей в меню"""
    await callback.answer()

@dp.callback_query(F.data == "reset_profile")
async def reset_profile(callback: CallbackQuery, state: FSMContext):
    """Сброс профиля"""
    # Создаем клавиатуру подтверждения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сбросить", callback_data="confirm_reset")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        "⚠️ **Вы уверены, что хотите сбросить свой профиль?**\n\n"
        "Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "statistics")
async def show_statistics(callback: CallbackQuery, state: FSMContext):
    """Показ статистики"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли анкета у пользователя
    if not await check_profile_exists(user_id):
        await callback.message.edit_text(
            "❌ **Сначала создайте профиль!**\n\n"
            "Для просмотра статистики необходимо заполнить анкету.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем статистику
    total_users = await db.get_users_count()
    viewed_count = len(viewed_users.get(user_id, []))
    
    # Получаем информацию о пользователе
    user = await db.get_user(user_id)
    
    # Формируем статистику
    text = f"📊 **Ваша статистика**\n\n"
    text += f"👤 **Ваш профиль:**\n"
    text += f"• Имя: {user['name']}\n"
    text += f"• Филиал: {user.get('branch', 'Не указан')}\n"
    text += f"• Должность: {user.get('job_title', 'Не указана')}\n\n"
    
    text += f"🔍 **Активность:**\n"
    text += f"• Просмотрено профилей: {viewed_count}\n"
    text += f"• Всего пользователей в системе: {total_users}\n\n"
    
    if viewed_count > 0:
        text += f"📈 **Прогресс:**\n"
        progress_percent = min(100, (viewed_count / max(1, total_users - 1)) * 100)
        text += f"• Просмотрено: {progress_percent:.1f}% от всех профилей\n"
        
        if progress_percent >= 100:
            text += f"• 🎉 Вы просмотрели всех пользователей!\n"
        elif progress_percent >= 50:
            text += f"• 🚀 Отличный прогресс!\n"
        elif progress_percent >= 25:
            text += f"• 👍 Хороший старт!\n"
        else:
            text += f"• 💪 Продолжайте знакомиться!\n"
    
    text += f"\n💡 **Совет:** Используйте поиск по имени для быстрого поиска конкретных людей!"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "confirm_reset")
async def confirm_reset(callback: CallbackQuery, state: FSMContext):
    """Подтверждение сброса профиля"""
    success = await db.delete_user(callback.from_user.id)
    
    if success:
        await callback.message.edit_text(
            "✅ **Профиль успешно удален!**\n\n"
            "Теперь вы можете создать новый профиль.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать профиль", callback_data="create_profile")]
            ])
        )
    else:
        await callback.message.edit_text("❌ Произошла ошибка при удалении профиля.")
    
    await callback.answer()


# Команды для административных функций
@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    """Команда /reset"""
    success = await db.delete_user(message.from_user.id)
    
    if success:
        await message.answer(MESSAGES['profile_reset'])
        await message.answer("📝 Давайте заполним вашу анкету!\n\nВведите ваше имя:")
        await state.set_state(ProfileStates.waiting_for_name)
    else:
        await message.answer("❌ Произошла ошибка при сбросе анкеты.")


@dp.message(Command("profile"))
async def cmd_profile(message: types.Message, state: FSMContext):
    """Команда /profile"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer(MESSAGES['profile_not_found'])
        return
    
    text = f"👤 **Ваш профиль**\n\n"
    text += f"Имя: {user['name']}\n"
    text += f"Филиал: {user['branch']}\n"
    text += f"Должность: {user['job_title']}\n"
    text += f"О себе: {user['about']}"
    
    if user.get('photo_file_id'):
        await message.answer_photo(
            photo=user['photo_file_id'],
            caption=text,
            parse_mode="Markdown"
        )
    else:
        await message.answer(text, parse_mode="Markdown")


@dp.message()
async def handle_unknown_message(message: types.Message, state: FSMContext):
    """Обработчик для всех необработанных сообщений"""
    logger.info(f"Необработанное сообщение от {message.from_user.id}: {message.text}")
    
    # Если пользователь в процессе создания профиля, предлагаем продолжить
    current_state = await state.get_state()
    if current_state in [ProfileStates.waiting_for_name, ProfileStates.waiting_for_branch, 
                        ProfileStates.waiting_for_job_title, ProfileStates.waiting_for_about, 
                        ProfileStates.waiting_for_photo]:
        await message.answer(
            "❓ Не понимаю эту команду.\n\n"
            "Пожалуйста, следуйте инструкциям для заполнения анкеты или используйте /cancel для отмены."
        )
    else:
        # Если пользователь не в процессе создания профиля, показываем главное меню
        user = await db.get_user(message.from_user.id)
        if user:
            await message.answer(
                "❓ Не понимаю эту команду.\n\n"
                "Используйте кнопки меню для навигации:",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await message.answer(
                "❓ Не понимаю эту команду.\n\n"
                "Для начала работы создайте профиль:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Создать анкету", callback_data="create_profile")]
                ])
            )


async def main():
    """Главная функция"""
    global BOT_ID
    
    # Получаем ID бота
    try:
        bot_info = await bot.get_me()
        BOT_ID = bot_info.id
        logger.info(f"ID бота: {BOT_ID}")
    except Exception as e:
        logger.error(f"Не удалось получить ID бота: {e}")
        BOT_ID = None
    
    # Инициализируем базу данных
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Запускаем бота
    logger.info("Запуск бота...")
    await dp.start_polling(bot)


async def send_like_notification_with_buttons(to_user_id: int, from_user_id: int):
    """Отправка уведомления о новом лайке с кнопками ответа"""
    try:
        # Проверяем, что получатель - не бот
        if BOT_ID and to_user_id == BOT_ID:
            logger.warning(f"Попытка отправить уведомление боту (ID: {to_user_id})")
            return False
            
        # Получаем информацию о пользователе, который поставил лайк
        contact_info = await db.get_user_contact_info(from_user_id)
        
        if not contact_info:
            logger.error(f"Не удалось получить информацию о пользователе {from_user_id}")
            return False
        
        await bot.send_message(
            to_user_id,
            f"💖 **Новый интерес!**\n\n"
            f"👤 {contact_info['name']} выразил желание познакомиться с вами!\n\n"
            f"🏢 **Филиал:** {contact_info['branch']}\n"
            f"💼 **Должность:** {contact_info['job_title']}\n"
            f"🆔 **ID для связи:** `{from_user_id}`\n\n"
            f"💡 Выберите действие:",
            reply_markup=get_response_keyboard(from_user_id)
        )
        logger.info(f"✅ Уведомление о лайке отправлено пользователю {to_user_id}")
        return True
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о лайке: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())
