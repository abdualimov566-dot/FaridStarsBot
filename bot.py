
import asyncio
import os
import sqlite3
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError(".env faylida BOT_TOKEN va ADMIN_ID bo'lishi kerak!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DB_NAME = "farid_stars.db"

PRODUCTS = {
    "stars": {
        "50": ("50 ⭐ Stars", 12000),
        "100": ("100 ⭐ Stars", 23000),
        "250": ("250 ⭐ Stars", 55000),
        "500": ("500 ⭐ Stars", 112000),
        "1000": ("1000 ⭐ Stars", 225000),
    },
    "premium": {
        "1": ("1 oylik Premium", 36000),
        "3": ("3 oylik Premium", 108000),
        "6": ("6 oylik Premium", 216000),
        "12": ("12 oylik Premium", 275000),
    },
    "gifts": {
        "heart": ("❤️", 4000),
        "bear": ("🧸", 4000),
        "flower": ("🌹", 7000),
        "ring": ("💍", 25000),
        "cake": ("🎂", 13000),
        "bouquet": ("💐", 13000),
        "rocket": ("🚀", 13000),
        "champagne": ("🍾", 13000),
        "trophy": ("🏆", 25000),
    }
}


class OrderState(StatesGroup):
    waiting_username = State()


def init_db():
    with sqlite3.connect(DB_NAME) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                product TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'Kutilmoqda'
            )
        """)

        columns = [
            row[1] for row in db.execute(
                "PRAGMA table_info(orders)"
            )
        ]

        if "username" not in columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN username TEXT NOT NULL DEFAULT ''"
            )

        if "price" not in columns:
            db.execute(
                "ALTER TABLE orders ADD COLUMN price INTEGER NOT NULL DEFAULT 0"
            )


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐ Stars"),
                KeyboardButton(text="💎 Premium")
            ],
            [KeyboardButton(text="🎁 Gifts")],
            [
                KeyboardButton(text="📋 Buyurtmalarim"),
                KeyboardButton(text="👨‍💻 Admin")
            ]
        ],
        resize_keyboard=True
    )


def product_keyboard(category):
    buttons = []

    for key, (name, price) in PRODUCTS[category].items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} | {price:,} so'm",
                callback_data=f"product:{category}:{key}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "⭐ FARID STARS PREMIUM ga xush kelibsiz!\n\n"
        "Kerakli xizmatni tanlang:",
        reply_markup=main_keyboard()
    )


@dp.message(F.text == "⭐ Stars")
async def stars_menu(message: Message):
    await message.answer(
        "⭐ Stars paketini tanlang:",
        reply_markup=product_keyboard("stars")
    )


@dp.message(F.text == "💎 Premium")
async def premium_menu(message: Message):
    await message.answer(
        "💎 Premium muddatini tanlang:",
        reply_markup=product_keyboard("premium")
    )


@dp.message(F.text == "🎁 Gifts")
async def gifts_menu(message: Message):
    await message.answer(
        "🎁 GIFTS KATALOGI\n\n"
        "O'zingizga yoqqan sovg'ani tanlang:",
        reply_markup=product_keyboard("gifts")
    )


@dp.callback_query(F.data.startswith("product:"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    _, category, key = callback.data.split(":")

    if category not in PRODUCTS or key not in PRODUCTS[category]:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    name, price = PRODUCTS[category][key]

    await state.update_data(product=name, price=price)
    await state.set_state(OrderState.waiting_username)

    await callback.message.answer(
        f"Tanlangan mahsulot: {name}\n"
        f"Narxi: {price:,} so'm\n\n"
        "📩 Telegram username'ingizni yuboring.\n"
        "Masalan: @username"
    )

    await callback.answer()


@dp.message(OrderState.waiting_username)
async def receive_username(message: Message, state: FSMContext):
    username = (message.text or "").strip().lstrip("@")

    if (
        not username
        or len(username) < 5
        or len(username) > 32
        or not username.replace("_", "").isalnum()
        or not username[0].isalpha()
    ):
        await message.answer(
            "❌ Username noto'g'ri. Masalan: @username."
        )
        return

    data = await state.get_data()

    with sqlite3.connect(DB_NAME) as db:
        cursor = db.execute(
            """
            INSERT INTO orders (user_id, username, product, price)
            VALUES (?, ?, ?, ?)
            """,
            (message.from_user.id, username, data["product"], data["price"])
        )
        order_id = cursor.lastrowid

    await state.clear()

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Tasdiqlash",
                callback_data=f"approve:{order_id}"
            ),
            InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data=f"reject:{order_id}"
            )
        ]]
    )

    admin_text = (
        f"🆕 YANGI BUYURTMA #{order_id}\n\n"
        f"👤 Mijoz: @{username}\n"
        f"🆔 Telegram ID: {message.from_user.id}\n"
        f"📦 Mahsulot: {data['product']}\n"
        f"💰 Narxi: {data['price']:,} so'm\n"
        "📌 Holati: Kutilmoqda"
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            admin_text,
            reply_markup=admin_keyboard
        )
    except Exception:
        logging.exception("Adminga xabar yuborilmadi")

    await message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"📦 {data['product']}\n"
        f"👤 @{username}\n"
        f"💰 {data['price']:,} so'm\n"
        f"🆔 Buyurtma: #{order_id}\n\n"
        "Admin buyurtmani ko'rib chiqadi.",
        reply_markup=main_keyboard()
    )


@dp.callback_query(F.data.startswith(("approve:", "reject:")))
async def manage_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    action, order_id = callback.data.split(":")
    order_id = int(order_id)

    new_status = (
        "Tasdiqlandi" if action == "approve"
        else "Bekor qilindi"
    )

    with sqlite3.connect(DB_NAME) as db:
        cursor = db.execute(
            """
            UPDATE orders SET status = ?
            WHERE id = ? AND status = 'Kutilmoqda'
            """,
            (new_status, order_id)
        )

        if cursor.rowcount == 0:
            await callback.answer(
                "Bu buyurtma avval ko'rib chiqilgan!",
                show_alert=True
            )
            return

        result = db.execute(
            "SELECT user_id, product FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

    if result is None:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    user_id, product = result

    try:
        await bot.send_message(
            user_id,
            f"📦 Buyurtmangiz: {product}\n"
            f"Holati: {new_status}"
        )
    except Exception:
        logging.exception("Mijozga xabar yuborilmadi")

    await callback.message.edit_text(
        callback.message.text + f"\n\n📌 Holati: {new_status}"
    )

    await callback.answer("Buyurtma yangilandi!")


@dp.message(F.text == "📋 Buyurtmalarim")
async def my_orders(message: Message):
    with sqlite3.connect(DB_NAME) as db:
        orders = db.execute(
            """
            SELECT id, product, price, status
            FROM orders
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 10
            """,
            (message.from_user.id,)
        ).fetchall()

    if not orders:
        await message.answer("Sizda hali buyurtmalar yo'q.")
        return

    result_text = "📋 Oxirgi buyurtmalaringiz:\n\n"

    for order_id, product, price, status in orders:
        result_text += (
            f"🆔 #{order_id}\n"
            f"📦 {product}\n"
            f"💰 {price:,} so'm\n"
            f"📌 {status}\n\n"
        )

    await message.answer(result_text)


@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: Message):
    await message.answer(
        "👨‍💻 Admin bilan bog'lanish:\n"
        "https://t.me/wunccy"
    )


async def main():
    init_db()
    print("FARID STARS PREMIUM ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
