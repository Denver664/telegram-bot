from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
import random
import logging

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Словник для зберігання стану гри для кожного користувача
games = {}
# Зберігання рекордів
records = {
    "guess_human": {"attempts": float("inf"), "username": "None"},
    "guess_bot": {"attempts": float("inf"), "username": "None"}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Вгадування людиною", callback_data="guess_human")],
        [InlineKeyboardButton("Вгадування ботом", callback_data="guess_bot")],
        [InlineKeyboardButton("Переглянути рекорди", callback_data="view_records")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Виберіть режим гри:", reply_markup=reply_markup)
    logger.info(f"User {update.effective_user.id} started the bot")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data
    logger.info(f"User {user_id} pressed: {data}")

    if data == "guess_human":
        games[user_id] = {"mode": "guess_human", "min": 1, "max": 100, "attempts": 0}
        await query.edit_message_text("Загадайте число від 1 до 100. Я спробую вгадати! Натискайте 'Вище' або 'Нижче'.")
        await make_guess(user_id, query, context)
    elif data == "guess_bot":
        games[user_id] = {"mode": "guess_bot", "number": random.randint(1, 100), "attempts": 0, "max_attempts": 10}
        await query.edit_message_text("Я загадав число від 1 до 100. Спробуй вгадати! Напишіть число.")
        logger.info(f"Generated number for user {user_id}: {games[user_id]['number']}")
    elif data == "view_records":
        record_human = f"Рекорд (Вгадування людиною): {records['guess_human']['attempts']} спроб. Рекордсмен: @{records['guess_human']['username']}"
        record_bot = f"Рекорд (Вгадування ботом): {records['guess_bot']['attempts']} спроб. Рекордсмен: @{records['guess_bot']['username']}"
        await query.edit_message_text(f"{record_human}\n{record_bot}")
    else:
        await callback_handler(update, context)

async def make_guess(user_id: int, query, context: ContextTypes.DEFAULT_TYPE):
    if user_id not in games or games[user_id].get("mode") != "guess_human":
        logger.warning(f"Invalid state for user {user_id}. Games: {games}")
        await query.edit_message_text("Помилка: почніть нову гру через /start")
        return

    games[user_id]["attempts"] += 1
    guess = random.randint(games[user_id]["min"], games[user_id]["max"])
    keyboard = [
        [InlineKeyboardButton("Вище", callback_data=f"higher_{guess}")],
        [InlineKeyboardButton("Нижче", callback_data=f"lower_{guess}")],
        [InlineKeyboardButton("Вгадав", callback_data=f"correct_{guess}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Моя спроба: {guess}. Натисни кнопку:", reply_markup=reply_markup)
    logger.info(f"User {user_id} guess: {guess}, range: [{games[user_id]['min']}, {games[user_id]['max']}]")

async def process_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.from_user.first_name

    if user_id not in games or games[user_id].get("mode") != "guess_bot":
        await update.message.reply_text("Спочатку виберіть режим через /start")
        logger.warning(f"User {user_id} tried to guess without mode")
        return

    try:
        user_guess = int(update.message.text.strip())
        if not 1 <= user_guess <= 100:
            await update.message.reply_text("Будь ласка, введи число від 1 до 100!")
            return

        games[user_id]["attempts"] += 1
        if games[user_id]["attempts"] > games[user_id]["max_attempts"]:
            await update.message.reply_text(f"Ви вичерпали {games[user_id]['max_attempts']} спроб. Почніть нову гру через /start.")
            del games[user_id]
            return

        target_number = games[user_id]["number"]
        logger.info(f"User {user_id} guess: {user_guess}, attempts: {games[user_id]['attempts']}")

        if user_guess == target_number:
            attempts = games[user_id]["attempts"]
            await update.message.reply_text(f"Вітаю! Ти вгадав число {target_number} за {attempts} спроб! Використовуй /start для нової гри.")
            if attempts < records["guess_bot"]["attempts"]:
                records["guess_bot"]["attempts"] = attempts
                if records["guess_bot"]["username"] == "None":
                    records["guess_bot"]["username"] = username or "Unknown"
                logger.info(f"New record by {username} in guess_bot: {attempts} attempts")
            del games[user_id]
        elif user_guess < target_number:
            await update.message.reply_text("Загадане число більше! Спробуй ще раз.")
        else:
            await update.message.reply_text("Загадане число менше! Спробуй ще раз.")
    except ValueError:
        await update.message.reply_text("Напишіть число від 1 до 100!")
        logger.error(f"ValueError for user {user_id}: {update.message.text}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data.split("_")
    logger.info(f"Callback from user {user_id}: {query.data}")

    if user_id not in games or games[user_id].get("mode") != "guess_human":
        logger.warning(f"Invalid state for user {user_id}. Games: {games}")
        await query.edit_message_text("Помилка: почніть нову гру через /start")
        return

    try:
        if len(data) != 2:
            raise ValueError("Неправильний формат даних")
        action, guess_str = data[0], data[1]
        guess = int(guess_str)
        logger.info(f"Processing action: {action}, guess: {guess}")

        if action == "higher":
            games[user_id]["min"] = guess + 1
            logger.info(f"Updated min to {games[user_id]['min']}")
        elif action == "lower":
            games[user_id]["max"] = guess - 1
            logger.info(f"Updated max to {games[user_id]['max']}")
        elif action == "correct":
            attempts = games[user_id]["attempts"]
            await query.edit_message_text(f"Я вгадав ваше число {guess} за {attempts} спроб! Використовуй /start для нової гри.")
            if attempts < records["guess_human"]["attempts"]:
                records["guess_human"]["attempts"] = attempts
                if records["guess_human"]["username"] == "None":
                    records["guess_human"]["username"] = username or "Unknown"
                logger.info(f"New record by {username} in guess_human: {attempts} attempts")
            del games[user_id]
            return

        if games[user_id]["min"] > games[user_id]["max"]:
            await query.edit_message_text("Помилка: неправильні дані. Почніть нову гру через /start")
            del games[user_id]
            return

        await make_guess(user_id, query, context)
    except Exception as e:
        logger.error(f"Error in callback_handler for user {user_id}: {str(e)}")
        await query.edit_message_text(f"Помилка: {str(e)}. Почніть нову гру через /start")

def main():
    application = ApplicationBuilder().token("7490288202:AAFBfI7q79h1U8z-7wRuLZWDIG9CP8kJ62A").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_guess))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
