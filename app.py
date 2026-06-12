# app.py — исправленная версия для Python 3.14+
import os
import threading
import asyncio
from flask import Flask
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from hobby_data import HOBBY_DESCRIPTIONS, QUESTIONS

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_BOT_TOKEN не установлена!")

user_data = {}

# ========== Обработчики бота (без изменений) ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"current_q": 0, "scores": {}}
    await update.message.reply_text(
        "🧙‍♀️ Привет! Я помогу тебе найти новое хобби!\n\n"
        "Нажми /next, чтобы начать опрос ➡️"
    )

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"current_q": 0, "scores": {}}
    current = user_data[user_id]["current_q"]
    if current >= len(QUESTIONS):
        await show_result(update, context)
        return
    question = QUESTIONS[current]
    options = question["options"]
    button_list = [[option] for option in options.keys()]
    reply_markup = ReplyKeyboardMarkup(button_list, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"**Вопрос {current + 1} из {len(QUESTIONS)}**\n\n{question['text']}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    answer = update.message.text
    if user_id not in user_data:
        await update.message.reply_text("Напиши /start, чтобы начать")
        return
    current = user_data[user_id]["current_q"]
    if current >= len(QUESTIONS):
        await show_result(update, context)
        return
    question = QUESTIONS[current]
    options = question["options"]
    if answer not in options:
        await update.message.reply_text("Пожалуйста, выбери вариант из кнопок 👇")
        return
    for cat_id, points in options[answer].items():
        user_data[user_id]["scores"][cat_id] = user_data[user_id]["scores"].get(cat_id, 0) + points
    user_data[user_id]["current_q"] += 1
    await next_question(update, context)

async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    scores = user_data[user_id]["scores"]
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_cats[:3]
    result_text = "🎉 **Твои топ-3 хобби** 🎉\n\n"
    for i, (cat_id, score) in enumerate(top3):
        if score > 0:
            result_text += f"**{i+1}. {HOBBY_DESCRIPTIONS[cat_id]}**\n\n"
    if all(score <= 0 for _, score in top3):
        result_text = "🤔 По твоим ответам сложно выбрать... Попробуй /start ещё раз!"
    await update.message.reply_text(result_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    if user_id in user_data:
        del user_data[user_id]

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    await update.message.reply_text("❌ Опрос отменён. Напиши /start, чтобы начать заново", reply_markup=ReplyKeyboardRemove())

# ========== Запуск бота в потоке с правильным event loop ==========
def run_bot():
    # Создаём новый event loop для этого потока (нужно для Python 3.14+)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("next", next_question))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    
    print("✅ Бот запущен и слушает сообщения...")
    # Запускаем polling в текущем event loop
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())
    loop.run_until_complete(application.updater.start_polling())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(application.shutdown())
        loop.close()

# ========== Flask приложение ==========
app_flask = Flask(__name__)

@app_flask.route('/')
def index():
    return "Telegram hobby bot is running!"

@app_flask.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host='0.0.0.0', port=port)