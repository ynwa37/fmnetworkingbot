"""
Telegram бот для знакомств
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN, MESSAGES
from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
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


# Временное хранилище для текущего просматриваемого профиля
current_viewing = {}

# Хранилище просмотренных пользователей для каждого пользователя
viewed_users = {}


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    # Проверяем, есть ли уже анкета у пользователя
    user = await db.get_user(message.from_user.id)
    
    if user:
        # Показываем главное меню
        await show_main_menu(message)
    else:
        # Показываем приветствие и начинаем заполнение анкеты
        await message.answer(MESSAGES['welcome'])
        await message.answer("📝 Давайте заполним вашу профессиональную анкету!\n\nВведите ваше имя:")
        await state.set_state(ProfileStates.waiting_for_name)


@dp.message(StateFilter(ProfileStates.waiting_for_name))
async def process_name(message: types.Message, state: FSMContext):
    """Обработка ввода имени"""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(name=name)
    await message.answer("🏢 Введите ваш филиал/отдел:")
    await state.set_state(ProfileStates.waiting_for_branch)


@dp.message(StateFilter(ProfileStates.waiting_for_branch))
async def process_branch(message: types.Message, state: FSMContext):
    """Обработка ввода филиала"""
    branch = message.text.strip()
    if len(branch) < 2:
        await message.answer("❌ Название филиала должно содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(branch=branch)
    await message.answer("💼 Введите вашу должность:")
    await state.set_state(ProfileStates.waiting_for_job_title)


@dp.message(StateFilter(ProfileStates.waiting_for_job_title))
async def process_job_title(message: types.Message, state: FSMContext):
    """Обработка ввода должности"""
    job_title = message.text.strip()
    if len(job_title) < 2:
        await message.answer("❌ Должность должна содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(job_title=job_title)
    await message.answer("📝 Расскажите о ваших профессиональных интересах, навыках и целях (свободный текст):")
    await state.set_state(ProfileStates.waiting_for_about)


@dp.message(StateFilter(ProfileStates.waiting_for_about))
async def process_about(message: types.Message, state: FSMContext):
    """Обработка ввода информации о себе"""
    about = message.text.strip()
    if len(about) < 10:
        await message.answer("❌ Расскажите о себе подробнее (минимум 10 символов). Попробуйте еще раз:")
        return
    
    await state.update_data(about=about)
    
    # Создаем клавиатуру для выбора фото
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
    ])
    
    await message.answer("📷 Хотите добавить фото к анкете?", reply_markup=keyboard)
    await state.set_state(ProfileStates.waiting_for_photo)


@dp.callback_query(F.data == "add_photo")
async def process_add_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора добавления фото"""
    await callback.message.edit_text("📷 Отправьте ваше фото:")
    await state.set_state(ProfileStates.waiting_for_photo)


@dp.callback_query(F.data == "skip_photo")
async def process_skip_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска фото"""
    await save_profile(callback.message, state, photo_file_id=None)
    await callback.answer()


@dp.message(StateFilter(ProfileStates.waiting_for_photo), F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработка загрузки фото"""
    photo_file_id = message.photo[-1].file_id
    await save_profile(message, state, photo_file_id)


@dp.message(StateFilter(ProfileStates.waiting_for_photo))
async def process_photo_invalid(message: types.Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания фото"""
    await message.answer("❌ Пожалуйста, отправьте фото или нажмите 'Пропустить'")


async def save_profile(message: types.Message, state: FSMContext, photo_file_id: str = None):
    """Сохранение профиля в базу данных"""
    data = await state.get_data()
    
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
        await message.answer(MESSAGES['profile_created'])
        await show_main_menu(message)
    else:
        await message.answer("❌ Произошла ошибка при сохранении анкеты. Попробуйте еще раз.")


def get_main_menu_keyboard():
    """Создание главного меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
        [InlineKeyboardButton(text="👀 Просмотренные", callback_data="viewed_list")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
        [InlineKeyboardButton(text="🔄 Сбросить анкету", callback_data="reset_profile")]
    ])
    return keyboard


async def show_main_menu(message: types.Message):
    """Показ главного меню"""
    await message.answer("🏠 Главное меню", reply_markup=get_main_menu_keyboard())


@dp.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    """Начало поиска"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли другие пользователи
    users_count = await db.get_users_count()
    if users_count < 2:
        await callback.message.edit_text(MESSAGES['no_profiles'])
        await callback.answer()
        return
    
    # Получаем список уже просмотренных пользователей
    user_viewed = viewed_users.get(user_id, [])
    
    # Получаем случайного пользователя, исключая просмотренных
    random_user = await db.get_random_user(user_id, user_viewed)
    if not random_user:
        # Если все пользователи просмотрены, сбрасываем список
        viewed_users[user_id] = []
        await callback.message.edit_text("🎉 Вы просмотрели всех пользователей! Список обновлен, попробуйте снова.")
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


async def show_profile_card(message: types.Message, user_data: dict):
    """Показ карточки профиля"""
    text = f"👤 **{user_data['name']}**\n"
    text += f"🏢 Филиал: {user_data['branch']}\n"
    text += f"💼 Должность: {user_data['job_title']}\n"
    text += f"📝 О себе: {user_data['about']}"
    
    if user_data.get('photo_file_id'):
        await message.answer_photo(
            photo=user_data['photo_file_id'],
            caption=text,
            parse_mode="Markdown",
            reply_markup=get_profile_card_keyboard()
        )
    else:
        await message.answer(
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
    
    # Добавляем профессиональную связь
    await db.add_like(user_id, viewed_user['telegram_id'])
    
    # Проверяем на профессиональное совпадение
    is_match = await db.check_match(user_id, viewed_user['telegram_id'])
    
    if is_match:
        # Получаем username для уведомления
        username = await db.get_user_username(viewed_user['telegram_id'])
        await callback.message.edit_text(f"🎉 {MESSAGES['match_found'].format(username)}")
        
        # Уведомляем другого пользователя о профессиональном совпадении
        other_username = await db.get_user_username(user_id)
        try:
            await bot.send_message(
                viewed_user['telegram_id'],
                f"🎉 {MESSAGES['match_found'].format(other_username)}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    else:
        await callback.message.edit_text(MESSAGES['like_sent'])
    
    # Удаляем из текущего просмотра
    if user_id in current_viewing:
        del current_viewing[user_id]
    
    await callback.answer()


@dp.callback_query(F.data == "next")
async def process_next(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Дальше'"""
    user_id = callback.from_user.id
    
    # Удаляем текущего пользователя из просмотра
    if user_id in current_viewing:
        del current_viewing[user_id]
    
    # Получаем список уже просмотренных пользователей
    user_viewed = viewed_users.get(user_id, [])
    
    # Ищем следующего пользователя, исключая просмотренных
    random_user = await db.get_random_user(user_id, user_viewed)
    if not random_user:
        # Если все пользователи просмотрены, сбрасываем список
        viewed_users[user_id] = []
        await callback.message.edit_text("🎉 Вы просмотрели всех пользователей! Список обновлен, попробуйте снова.")
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
    
    # Сбрасываем список просмотренных пользователей при возврате в меню
    if user_id in viewed_users:
        del viewed_users[user_id]
    
    await callback.message.edit_text("🏠 Главное меню", reply_markup=get_main_menu_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "viewed_list")
async def show_viewed_list(callback: CallbackQuery, state: FSMContext):
    """Показ списка просмотренных пользователей"""
    user_id = callback.from_user.id
    user_viewed = viewed_users.get(user_id, [])
    
    if not user_viewed:
        await callback.message.edit_text(
            "👀 Вы еще никого не просматривали.\n\nНажмите '🔍 Найти людей' чтобы начать поиск!",
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
    text = f"👀 **Просмотренные пользователи** ({len(viewed_users_info)}):\n\n"
    
    for i, user in enumerate(viewed_users_info, 1):
        text += f"{i}. **{user['name']}**\n"
        text += f"   🏢 {user['branch']} | 💼 {user['job_title']}\n"
        text += f"   📝 {user['about'][:50]}...\n\n"
    
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
        "✅ Список просмотренных пользователей очищен!\n\nТеперь при поиске будут показаны все доступные профили.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти людей", callback_data="search")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery, state: FSMContext):
    """Показ профиля пользователя"""
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text(MESSAGES['profile_not_found'])
        await callback.answer()
        return
    
    text = f"👤 **Ваш профиль**\n\n"
    text += f"Имя: {user['name']}\n"
    text += f"Филиал: {user['branch']}\n"
    text += f"Должность: {user['job_title']}\n"
    text += f"О себе: {user['about']}"
    
    if user.get('photo_file_id'):
        await callback.message.answer_photo(
            photo=user['photo_file_id'],
            caption=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
    
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
        "⚠️ Вы уверены, что хотите сбросить свою анкету? Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "confirm_reset")
async def confirm_reset(callback: CallbackQuery, state: FSMContext):
    """Подтверждение сброса профиля"""
    success = await db.delete_user(callback.from_user.id)
    
    if success:
        await callback.message.edit_text(MESSAGES['profile_reset'])
        await asyncio.sleep(2)
        await callback.message.edit_text(MESSAGES['welcome'])
        await callback.message.answer("📝 Давайте заполним вашу профессиональную анкету!\n\nВведите ваше имя:")
        await state.set_state(ProfileStates.waiting_for_name)
    else:
        await callback.message.edit_text("❌ Произошла ошибка при сбросе анкеты.")
    
    await callback.answer()


# Команды для административных функций
@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    """Команда /reset"""
    success = await db.delete_user(message.from_user.id)
    
    if success:
        await message.answer(MESSAGES['profile_reset'])
        await message.answer("📝 Давайте заполним вашу профессиональную анкету!\n\nВведите ваше имя:")
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


async def main():
    """Главная функция"""
    # Инициализируем базу данных
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Запускаем бота
    logger.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
