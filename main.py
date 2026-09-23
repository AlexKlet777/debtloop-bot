import json
import logging
import os
import time

import telebot
from telebot import types
from dotenv import load_dotenv

from netting import find_debt_cycle, calculate_cycle_netting

load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN environment variable is not set")

bot = telebot.TeleBot(TOKEN)

logging.basicConfig(filename="errors.log", level=logging.ERROR)

DEBTS_FILE = "debts.json"


def load_debts():
    if not os.path.exists(DEBTS_FILE):
        return []

    with open(DEBTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    migrated = []
    for index, debt in enumerate(data, start=1):
        item = dict(debt)
        item.setdefault("id", index)
        # Legacy records had no confirmation state. Preserve them as confirmed.
        item.setdefault("status", "confirmed")
        migrated.append(item)

    return migrated


debts = load_debts()


def save_debts():
    with open(DEBTS_FILE, "w", encoding="utf-8") as f:
        json.dump(debts, f, ensure_ascii=False, indent=2)


def get_username(message):
    return message.from_user.username


def next_debt_id():
    return max((d.get("id", 0) for d in debts), default=0) + 1


def money(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,.2f}".rstrip("0").rstrip(".")


@bot.message_handler(commands=["start"])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("/owe"),
        types.KeyboardButton("/debts"),
        types.KeyboardButton("/credits"),
        types.KeyboardButton("/netting"),
        types.KeyboardButton("/demo"),
        types.KeyboardButton("/help"),
    )

    bot.send_message(
        message.chat.id,
        (
            "DebtLoop PoC\n\n"
            "B2B circular-debt detection and multilateral netting.\n\n"
            "Use /demo for the investor demo or /help for commands."
        ),
        reply_markup=markup,
    )


@bot.message_handler(commands=["help"])
def show_help(message):
    bot.send_message(
        message.chat.id,
        (
            "Commands:\n"
            "/owe @username amount — create a debt\n"
            "/confirm ID — confirm a debt addressed to you\n"
            "/reject ID — reject it\n"
            "/paid ID — mark a confirmed debt as paid\n"
            "/debts — debts you owe\n"
            "/credits — debts owed to you\n"
            "/netting — find a confirmed circular debt and calculate netting\n"
            "/demo — run the built-in B2B example"
        ),
    )


@bot.message_handler(commands=["owe"])
def add_debt(message):
    username = get_username(message)
    if not username:
        bot.send_message(
            message.chat.id,
            "Please set a Telegram username first. Debt confirmation uses usernames.",
        )
        return

    parts = message.text.split()

    if len(parts) != 3:
        bot.send_message(message.chat.id, "Format: /owe @username amount")
        return

    to_user = parts[1].lstrip("@")

    if to_user == username:
        bot.send_message(message.chat.id, "You cannot create a debt to yourself.")
        return

    try:
        amount = float(parts[2].replace(",", "."))
    except ValueError:
        bot.send_message(message.chat.id, "Amount must be a number.")
        return

    if amount <= 0:
        bot.send_message(message.chat.id, "Amount must be greater than zero.")
        return

    debt = {
        "id": next_debt_id(),
        "from": username,
        "to": to_user,
        "amount": amount,
        "status": "pending",
    }

    debts.append(debt)
    save_debts()

    bot.send_message(
        message.chat.id,
        (
            f'Debt #{debt["id"]} created:\n'
            f'@{username} → @{to_user}: {money(amount)}\n'
            "Status: pending confirmation."
        ),
    )


@bot.message_handler(commands=["confirm"])
def confirm_debt(message):
    username = get_username(message)
    parts = message.text.split()

    if not username or len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Format: /confirm ID")
        return

    debt_id = int(parts[1])

    for debt in debts:
        if (
            debt.get("id") == debt_id
            and debt.get("to") == username
            and debt.get("status") == "pending"
        ):
            debt["status"] = "confirmed"
            save_debts()
            bot.send_message(message.chat.id, f"Debt #{debt_id} confirmed.")
            return

    bot.send_message(
        message.chat.id,
        "Pending debt not found, or you are not the recipient.",
    )


@bot.message_handler(commands=["reject"])
def reject_debt(message):
    username = get_username(message)
    parts = message.text.split()

    if not username or len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Format: /reject ID")
        return

    debt_id = int(parts[1])

    for debt in debts:
        if (
            debt.get("id") == debt_id
            and debt.get("to") == username
            and debt.get("status") == "pending"
        ):
            debt["status"] = "rejected"
            save_debts()
            bot.send_message(message.chat.id, f"Debt #{debt_id} rejected.")
            return

    bot.send_message(
        message.chat.id,
        "Pending debt not found, or you are not the recipient.",
    )


@bot.message_handler(commands=["paid"])
def mark_paid(message):
    username = get_username(message)
    parts = message.text.split()

    if not username or len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Format: /paid ID")
        return

    debt_id = int(parts[1])

    for debt in debts:
        if (
            debt.get("id") == debt_id
            and username in (debt.get("from"), debt.get("to"))
            and debt.get("status") == "confirmed"
        ):
            debt["status"] = "paid"
            save_debts()
            bot.send_message(message.chat.id, f"Debt #{debt_id} marked as paid.")
            return

    bot.send_message(message.chat.id, "Confirmed debt not found.")


@bot.message_handler(commands=["debts"])
def list_debts(message):
    username = get_username(message)

    if not username:
        bot.send_message(message.chat.id, "Please set a Telegram username first.")
        return

    rows = [
        d
        for d in debts
        if d.get("from") == username and d.get("status") in ("pending", "confirmed")
    ]

    if not rows:
        bot.send_message(message.chat.id, "You have no active debts.")
        return

    msg = "You owe:\n"
    for debt in rows:
        msg += (
            f'#{debt["id"]} → @{debt["to"]}: '
            f'{money(debt["amount"])} ({debt["status"]})\n'
        )

    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=["credits"])
def list_credits(message):
    username = get_username(message)

    if not username:
        bot.send_message(message.chat.id, "Please set a Telegram username first.")
        return

    rows = [
        d
        for d in debts
        if d.get("to") == username and d.get("status") in ("pending", "confirmed")
    ]

    if not rows:
        bot.send_message(message.chat.id, "No active receivables found.")
        return

    msg = "Owed to you:\n"
    for debt in rows:
        msg += (
            f'#{debt["id"]} ← @{debt["from"]}: '
            f'{money(debt["amount"])} ({debt["status"]})\n'
        )

    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=["netting"])
def show_netting(message):
    active = [d for d in debts if d.get("status") == "confirmed"]
    cycle = find_debt_cycle(active)

    if not cycle:
        bot.send_message(message.chat.id, "No confirmed circular debt found.")
        return

    result = calculate_cycle_netting(cycle)

    msg = "🔄 CIRCULAR DEBT DETECTED\n\nBEFORE NETTING:\n"
    for debt in cycle:
        msg += (
            f'@{debt["from"]} → @{debt["to"]}: '
            f'{money(debt["amount"])}\n'
        )

    msg += (
        f'\nMaximum netting per link: '
        f'{money(result["netting_amount_per_link"])}\n\n'
        "AFTER NETTING:\n"
    )

    for debt in result["residual_debts"]:
        msg += (
            f'@{debt["from"]} → @{debt["to"]}: '
            f'{money(debt["after"])}\n'
        )

    msg += (
        f'\nGross obligations before: {money(result["total_before"])}'
        f'\nGross obligations after: {money(result["total_after"])}'
        f'\nGross debt eliminated: {money(result["debt_eliminated"])}'
        "\n\nThis is a netting proposal only; no balances are changed automatically."
    )

    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=["demo"])
def show_demo(message):
    demo_debts = [
        {"from": "Company A", "to": "Company B", "amount": 100000},
        {"from": "Company B", "to": "Company C", "amount": 80000},
        {"from": "Company C", "to": "Company A", "amount": 70000},
    ]

    cycle = find_debt_cycle(demo_debts)
    result = calculate_cycle_netting(cycle)

    msg = (
        "DEBTLOOP B2B DEMO\n\n"
        "Company A → Company B: $100,000\n"
        "Company B → Company C: $80,000\n"
        "Company C → Company A: $70,000\n\n"
        f'Maximum netting per link: ${money(result["netting_amount_per_link"])}\n\n'
        "Residual obligations:\n"
    )

    for debt in result["residual_debts"]:
        msg += (
            f'{debt["from"]} → {debt["to"]}: '
            f'${money(debt["after"])}\n'
        )

    msg += (
        f'\nGross obligations before: ${money(result["total_before"])}'
        f'\nGross obligations after: ${money(result["total_after"])}'
        f'\nGross debt eliminated: ${money(result["debt_eliminated"])}'
    )

    bot.send_message(message.chat.id, msg)


print("DebtLoop bot started...")

while True:
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception:
        logging.exception("Polling error")
        time.sleep(10)
