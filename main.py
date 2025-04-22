import telebot
from telebot import types
import json
import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем .env

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

DEBTS_FILE = "debts.json"

if os.path.exists(DEBTS_FILE):
    with open(DEBTS_FILE, "r") as f:
        debts = json.load(f)
else:
    debts = []

def save_debts():
    with open(DEBTS_FILE, "w") as f:
        json.dump(debts, f, ensure_ascii=False, indent=2)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("/owe @username сумма"),
               types.KeyboardButton("/debts"), types.KeyboardButton("/help"))
    bot.send_message(
        message.chat.id,
        "Привет! Я бот для закрытия долгов через круг.\n\n📌 Команды:\n/owe @username сумма — записать долг\n/debts — показать долги\n/help — помощь",
        reply_markup=markup)

@bot.message_handler(commands=['help'])
def show_help(message):
    bot.reply_to(
        message,
        "📌 Инструкция:\n/owe @username сумма — записать долг\n/debts — показать список долгов\nЕсли будет замкнутый круг — бот автоматически его закроет."
    )

@bot.message_handler(commands=['debts'])
def list_debts(message):
    if not debts:
        bot.reply_to(message, "Нет записанных долгов.")
    else:
        msg = "📋 Текущие долги:\n"
        for d in debts:
            msg += f"@{d['from']} должен(а) @{d['to']} {d['amount']}₽\n"
        bot.reply_to(message, msg)

@bot.message_handler(commands=['owe'])
def handle_owe(message):
    parts = message.text.strip().split()
    if len(parts) != 3:
        bot.reply_to(message, "Формат: /owe @username сумма")
        return

    from_user = message.from_user.username
    to_user = parts[1].replace("@", "")

    if from_user == to_user:
        bot.reply_to(message, "Нельзя записать долг самому себе 🤔")
        return

    try:
        amount = float(parts[2])
    except ValueError:
        bot.reply_to(message, "Сумма должна быть числом")
        return

    if not from_user:
        bot.reply_to(
            message,
            "У вас не указан username в Telegram. Зайдите в настройки и укажите его."
        )
        return

    debts.append({'from': from_user, 'to': to_user, 'amount': amount})
    save_debts()
    bot.reply_to(message,
                 f"Записано: @{from_user} должен(а) @{to_user} {amount}₽")

    check_for_loops(message)

def check_for_loops(message):
    found_loop = False
    for d1 in debts[:]:
        for d2 in debts:
            if d1['to'] == d2['from'] and d2['to'] != d1['from']:
                for d3 in debts:
                    if d3['to'] == d1['from'] and d3['from'] == d2['to']:
                        amount = min(d1['amount'], d2['amount'], d3['amount'])
                        for d in [d1, d2, d3]:
                            d['amount'] -= amount
                            if d['amount'] <= 0 and d in debts:
                                debts.remove(d)
                        save_debts()
                        msg = (
                            f"🔁 Найден круг! Долг на {amount}₽ закрыт между участниками: \n"
                            f"@{d1['from']} → @{d1['to']} → @{d2['to']} → @{d1['from']}"
                        )
                        bot.send_message(chat_id=message.chat.id, text=msg)
                        found_loop = True
                        break
                if found_loop:
                    break
        if found_loop:
            break

print("Бот запущен...")
bot.polling()
