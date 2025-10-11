import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем папку для изображений если её нет
os.makedirs('user_images', exist_ok=True)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('images.db')
    cursor = conn.cursor()
    
    # Проверяем существование таблицы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            file_path TEXT,
            image_name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Проверяем существование колонки image_name и добавляем если её нет
    try:
        cursor.execute("SELECT image_name FROM user_images LIMIT 1")
    except sqlite3.OperationalError:
        # Колонки нет, добавляем её
        cursor.execute('ALTER TABLE user_images ADD COLUMN image_name TEXT')
    
    conn.commit()
    conn.close()

# Сохранение информации об изображении в БД
def save_image_info(user_id, file_id, file_path, image_name=None):
    conn = sqlite3.connect('images.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_images (user_id, file_id, file_path, image_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, file_id, file_path, image_name))
    conn.commit()
    conn.close()

# Получение всех изображений пользователя
def get_user_images(user_id):
    conn = sqlite3.connect('images.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, file_id, file_path, image_name FROM user_images 
        WHERE user_id = ? ORDER BY timestamp DESC
    ''', (user_id,))
    images = cursor.fetchall()
    conn.close()
    return images

# Получить изображение по ID
def get_image_by_id(user_id, image_id):
    conn = sqlite3.connect('images.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, file_id, file_path, image_name FROM user_images 
        WHERE user_id = ? AND id = ?
    ''', (user_id, image_id))
    image = cursor.fetchone()
    conn.close()
    return image

# Простая клавиатура с поиском
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📸 Мои изображения"), KeyboardButton("🔍 Поиск фото")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура для отмены поиска
def get_search_keyboard():
    keyboard = [
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '👋 Привет! Я бот для хранения изображений.\n\n'
        '📸 **Просто отправь мне фото** - я его сохраню\n'
        '📝 **Хочешь дать название?** Напиши текст вместе с фото\n\n'
        '💡 **Быстрые команды:**\n'
        '• "📸 Мои изображения" - все твои фото\n'
        '• "🔍 Поиск фото" - найти по названию\n'
        '• "❓ Помощь" - справка по командам',
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '📖 **Как пользоваться:**\n\n'
        '💾 **Загрузка:**\n'
        '• Просто отправь фото - сохраню без названия\n'
        '• Отправь фото с подписью - сохраню с названием\n\n'
        '📁 **Просмотр и поиск:**\n'
        '• "📸 Мои изображения" - все твои фото\n'
        '• "🔍 Поиск фото" - найти по названию\n'
        '• /get ID - получить фото по номеру\n'
        '• /find название - поиск по названию\n\n'
        '⚡ **Используй кнопки ниже для быстрого доступа!**',
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

# Начать поиск
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '🔍 **Поиск изображений**\n\n'
        'Введи название или часть названия изображения:\n'
        '(например: "котик", "отпуск", "документ")',
        reply_markup=get_search_keyboard()
    )

# Обработка изображений с текстом (названием)
async def handle_photo_with_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        photo = update.message.photo[-1]
        image_name = update.message.caption
        
        # Получаем файл
        photo_file = await photo.get_file()
        
        # Создаем уникальное имя файла
        file_extension = '.jpg'
        filename = f"user_{user_id}_{photo.file_id}{file_extension}"
        file_path = os.path.join('user_images', filename)
        
        # Скачиваем и сохраняем файл
        await photo_file.download_to_drive(file_path)
        
        # Сохраняем информацию в БД
        save_image_info(user_id, photo.file_id, file_path, image_name)
        
        await update.message.reply_text(
            f'✅ Изображение сохранено!\n'
            f'📝 Название: {image_name}\n'
            f'🆔 ID: {len(get_user_images(user_id))}',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in handle_photo_with_caption: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка при сохранении изображения',
            reply_markup=get_main_keyboard()
        )

# Обработка изображений без текста
async def handle_photo_without_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        photo = update.message.photo[-1]
        
        # Получаем файл
        photo_file = await photo.get_file()
        
        # Создаем уникальное имя файла
        file_extension = '.jpg'
        filename = f"user_{user_id}_{photo.file_id}{file_extension}"
        file_path = os.path.join('user_images', filename)
        
        # Скачиваем и сохраняем файл
        await photo_file.download_to_drive(file_path)
        
        # Сохраняем информацию в БД
        save_image_info(user_id, photo.file_id, file_path)
        
        await update.message.reply_text(
            f'✅ Изображение сохранено!\n'
            f'🆔 ID: {len(get_user_images(user_id))}\n'
            f'💡 Напиши текст к следующему фото - так будет легче найти!',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in handle_photo_without_caption: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка при сохранении изображения',
            reply_markup=get_main_keyboard()
        )

# Показать все изображения пользователя
async def my_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        images = get_user_images(user_id)
        
        if not images:
            await update.message.reply_text(
                '📭 У тебя пока нет сохраненных изображений.\n'
                'Просто отправь мне фото! 📸',
                reply_markup=get_main_keyboard()
            )
            return
        
        message = "📸 **Твои изображения:**\n\n"
        for i, (img_id, file_id, file_path, image_name) in enumerate(images, 1):
            name = image_name if image_name else f"Без названия"
            message += f"{i}. {name} (ID: {img_id})\n"
        
        message += "\n💡 **Чтобы получить изображение:**\n"
        message += "• Используй /get ID (например: /get 1)\n"
        message += "• Или нажми кнопку '🔍 Поиск фото' для поиска по названию"
        
        await update.message.reply_text(
            message,
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in my_images: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка при получении списка изображений',
            reply_markup=get_main_keyboard()
        )

# Получить изображение по ID
async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        
        if not context.args:
            await update.message.reply_text(
                '❌ Укажи ID изображения. Например: /get 1\n'
                '💡 Используй /myimages чтобы посмотреть ID',
                reply_markup=get_main_keyboard()
            )
            return
        
        image_id = int(context.args[0])
        image = get_image_by_id(user_id, image_id)
        
        if not image:
            await update.message.reply_text(
                f"❌ Изображение с ID {image_id} не найдено",
                reply_markup=get_main_keyboard()
            )
            return
        
        img_id, file_id, file_path, image_name = image
        
        # Отправляем изображение
        with open(file_path, 'rb') as photo:
            caption = f"📸 {image_name}" if image_name else f"Изображение ID: {img_id}"
            await update.message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=get_main_keyboard()
            )
            
    except ValueError:
        await update.message.reply_text(
            '❌ Введи нормальный ID (цифру)',
            reply_markup=get_main_keyboard()
        )
    except FileNotFoundError:
        await update.message.reply_text(
            '❌ Файл изображения не найден',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in get_image: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка при отправке изображения',
            reply_markup=get_main_keyboard()
        )

# Поиск по названию (команда)
async def find_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        
        if not context.args:
            await update.message.reply_text(
                '❌ Укажи что искать. Например: /find котик\n'
                '💡 Или используй кнопку "🔍 Поиск фото"',
                reply_markup=get_main_keyboard()
            )
            return
        
        search_term = ' '.join(context.args).lower()
        await perform_search(update, user_id, search_term)
        
    except Exception as e:
        logger.error(f"Error in find_images: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка при поиске',
            reply_markup=get_main_keyboard()
        )

# Выполнить поиск и показать результаты
async def perform_search(update, user_id, search_term):
    images = get_user_images(user_id)
    
    # Ищем по названиям
    found_images = []
    for img in images:
        img_id, file_id, file_path, image_name = img
        if image_name and search_term in image_name.lower():
            found_images.append(img)
    
    if not found_images:
        await update.message.reply_text(
            f'🔍 По запросу "{search_term}" ничего не найдено\n\n'
            f'💡 Попробуй:\n'
            f'• Другое название\n'
            f'• Часть названия\n'
            f'• Посмотреть все фото через "📸 Мои изображения"',
            reply_markup=get_main_keyboard()
        )
        return
    
    message = f"🔍 **Найдено по запросу '{search_term}':**\n\n"
    for i, (img_id, file_id, file_path, image_name) in enumerate(found_images, 1):
        message += f"{i}. {image_name} (ID: {img_id})\n"
    
    message += f"\n💡 **Чтобы получить изображение:**\n"
    message += f"• Используй /get ID (например: /get {found_images[0][0]})\n"
    message += f"• Или продолжай поиск"
    
    await update.message.reply_text(
        message,
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.message.from_user.id
        
        if text == "📸 Мои изображения":
            await my_images(update, context)
        elif text == "🔍 Поиск фото":
            await start_search(update, context)
        elif text == "❓ Помощь":
            await help_command(update, context)
        elif text == "🔙 Назад":
            await update.message.reply_text(
                "👌 Возвращаемся в главное меню",
                reply_markup=get_main_keyboard()
            )
        else:
            # Если пользователь в режиме поиска (отправил текст после нажатия кнопки поиска)
            if update.message.reply_to_message and "поиск" in update.message.reply_to_message.text.lower():
                await perform_search(update, user_id, text)
            else:
                await update.message.reply_text(
                    '🤔 Не понял команду. Используй кнопки ниже или отправь фото! 📸\n\n'
                    '💡 **Доступные команды:**\n'
                    '/start - начать работу\n'
                    '/myimages - мои изображения\n'
                    '/get ID - получить изображение\n'
                    '/find название - поиск по названию\n'
                    '/help - помощь',
                    reply_markup=get_main_keyboard()
                )
    except Exception as e:
        logger.error(f"Error in handle_text: {e}")
        await update.message.reply_text(
            '❌ Произошла ошибка',
            reply_markup=get_main_keyboard()
        )

# Основная функция
def main():
    # Инициализация БД (важно сделать это в начале)
    init_db()
    print("✅ База данных инициализирована")
    
    # Создаем приложение
    application = Application.builder().token("7727936798:AAHccQUPUSAXEACMZ9xJZiif3wkpWXdOE4A").build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myimages", my_images))
    application.add_handler(CommandHandler("get", get_image))
    application.add_handler(CommandHandler("find", find_images))
    
    # Обработчики фото (с подписью и без)
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_with_caption))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.CAPTION, handle_photo_without_caption))
    
    # Обработчик текста
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    print("✅ Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == '__main__':
    main()
