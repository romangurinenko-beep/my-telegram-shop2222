# -*- coding: utf-8 -*-

# --- БЛОК 1: ІМПОРТИ ТА НАЛАШТУВАННЯ ---
import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.strategy import FSMStrategy  # <-- ОСЬ ЦЕЙ РЯДОК
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Налаштовуємо логування для відстеження роботи бота
logging.basicConfig(level=logging.INFO)

# --- БЛОК 2: КОНФІГУРАЦІЯ ---
# !!! ВСТАВТЕ СЮДИ ВАШ АКТУАЛЬНИЙ ТОКЕН, ОТРИМАНИЙ ВІД @BotFather !!!
BOT_TOKEN = "8491104942:AAHR5qea7wy7pLz4QpnC3jPUIZ4gAyi3J0w" 

# ID каналу, отриманий від @userinfobot
CHANNEL_ID = -1003030288382 
ADMIN_ID = 715211707
WEB_SERVER_HOST = "https://my-telegram-shop2222.onrender.com"  # Ваше посилання з Render
WEB_SERVER_PORT = int(os.environ.get('PORT', 8080))
# --- НОВЕ: Лічильник замовлень ---
ORDER_COUNTER = 1000

# Ініціалізація
bot = Bot(token=BOT_TOKEN)
# Встановлюємо FSMStrategy.CHAT, щоб стани були окремими для кожного чату
dp = Dispatcher(fsm_strategy=FSMStrategy.CHAT)




# --- БЛОК 3: ДАНІ (ТОВАРИ, ТЕКСТИ) ---
PRODUCTS = {
    "1": {
        "name": "Олівець синій",
        "short_desc": "Дуже гарний олівець який красиво пише.",
        "full_desc": "Олівець — це інструмент для письма, малювання або креслення...",
        "photo": "images/1.JPG",
        "prices": [
            {"quantity": 1, "price": 0.3},
            {"quantity": 3, "price": 0.5},
            {"quantity": 5, "price": 0.12}
        ]
    },
    "2": {
        "name": "Чашка червона",
        "short_desc": "Дуже гарна чашка з якої приємно пити.",
        "full_desc": "Невелика посудина (найчастіше з ручкою)...",
        "photo": "images/2.JPG",
        "prices": [
            {"quantity": 1, "price": 0.2},
            {"quantity": 3, "price": 0.3},
            {"quantity": 5, "price": 0.8}
        ]
    },
    "3": {
        "name": "Ручка фіолетова",
        "short_desc": "Дуже гарна ручка з гарним почерком в комплекті.",
        "full_desc": "Ручка — це канцелярське приладдя для залишення чорнильного сліду...",
        "photo": "images/3.JPG",
        "prices": [
            {"quantity": 1, "price": 0.3},
            {"quantity": 3, "price": 0.5},
            {"quantity": 5, "price": 0.11}
        ]
    },
    "4": {
        "name": "Пенал різнокольоровий",
        "short_desc": "Пенал офігєнний заряжений на позитивні емоції.",
        "full_desc": "Пенал — це невеликий футляр, контейнер або коробочка...",
        "photo": "images/4.JPG",
        "prices": [
            {"quantity": 1, "price": 0.3},
            {"quantity": 3, "price": 0.5},
            {"quantity": 5, "price": 0.11}
        ]
    },
    "5": {
        "name": "Лінійка довга",
        "short_desc": "Для вимірювання свого его.",
        "full_desc": "Лінійка – це простий вимірювальний інструмент...",
        "photo": "images/5.JPG",
        "prices": [
            {"quantity": 1, "price": 0.9},
            {"quantity": 3, "price": 1.6},
            {"quantity": 5, "price": 2.5}
        ]
    }
}

# Тексти для інформаційних розділів
TEXT_SHIPPING = "<b>🚚 Доставка</b>\n\nЗдійснюється перевізником Нової пошти на відділення або поштомат."
TEXT_PAYMENT = "<b>💳 Оплата</b>\n\nЗдійснюється за допомогою криптовалюти, USDC, USDT."
TEXT_RULES = "<b>📜 Правила</b>\n\nПоводимо себе чємно і нікому не грубіянимо."

# Зберігаємо кошики користувачів в пам'яті
user_carts = {}

# --- НОВЕ: Словник для відстеження очікувань в каналі ---
channel_context = {}


# --- БЛОК 4: СТАНИ FSM ---
class OrderState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_city = State()
    waiting_for_post = State()
    waiting_for_payment_confirmation = State()

# --- БЛОК 5: КЛАВІАТУРИ ---
main_menu_button = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Меню ☰")]], resize_keyboard=True)

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Товари 🛍️", callback_data="show_products")],
        [InlineKeyboardButton(text="Доставка 🚚", callback_data="show_shipping"), InlineKeyboardButton(text="Оплата 💳", callback_data="show_payment")],
        [InlineKeyboardButton(text="Правила 📜", callback_data="show_rules")]
    ])

def get_cart_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оформити замовлення ✔️", callback_data="checkout")],
        [InlineKeyboardButton(text="Продовжити покупки 🛍️", callback_data="show_products")]
    ])

# --- БЛОК 6: ГОЛОВНІ ОБРОБНИКИ (START, MENU) ---
@dp.message(Command("start"))
async def handle_start(message: types.Message):
    await message.answer("👋 Вітаємо у нашому магазині!", reply_markup=main_menu_button)

@dp.message(F.text == "Меню ☰")
async def handle_menu_button(message: types.Message):
    await message.answer("Оберіть потрібний розділ:", reply_markup=get_main_menu_keyboard())

# --- БЛОК 7: ОБРОБНИКИ ІНФОРМАЦІЙНИХ РОЗДІЛІВ ---
@dp.callback_query(F.data.in_({"show_shipping", "show_payment", "show_rules", "back_to_main_menu"}))
async def show_info_sections(callback: types.CallbackQuery):
    text = ""
    if callback.data == "show_shipping": text = TEXT_SHIPPING
    elif callback.data == "show_payment": text = TEXT_PAYMENT
    elif callback.data == "show_rules": text = TEXT_RULES
    else: text = "Оберіть потрібний розділ:"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

# --- БЛОК 8: ОБРОБНИКИ КАТАЛОГУ ТОВАРІВ ---
@dp.callback_query(F.data == "show_products")
async def show_product_list(callback: types.CallbackQuery):
    buttons = []
    for product_id, data in PRODUCTS.items():
        buttons.append([InlineKeyboardButton(text=f"Детальніше про '{data['name']}'", callback_data=f"product_details:{product_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до меню", callback_data="back_to_main_menu")])
    
    await callback.message.edit_text("<b>Наші товари:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("product_details:"))
async def show_product_details(callback: types.CallbackQuery):
    product_id = callback.data.split(":")[1]
    data = PRODUCTS[product_id]
    
    text = f"<b>{data['name']}</b>\n\n{data['full_desc']}"
    photo = FSInputFile(data['photo'])
    
    buttons = []
    for price_info in data['prices']:
        quantity = price_info['quantity']
        price = price_info['price']
        buttons.append([InlineKeyboardButton(text=f"Купити {quantity} шт. - {price}$", callback_data=f"add_to_cart:{product_id}:{quantity}:{price}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до товарів", callback_data="show_products")])
    
    await callback.message.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    try: await callback.message.delete()
    except Exception: pass

# --- БЛОК 9: ОБРОБНИКИ КОШИКА ---
@dp.callback_query(F.data.startswith("add_to_cart:"))
async def add_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    product_id, quantity, price = parts[1], int(parts[2]), float(parts[3])

    if user_id not in user_carts:
        user_carts[user_id] = {}
    
    cart_item_key = f"{product_id}_{quantity}" 
    
    user_carts[user_id][cart_item_key] = {'product_id': product_id, 'quantity': quantity, 'price': price}

    product_name = PRODUCTS[product_id]['name']
    await callback.answer(f"Додано: {product_name} ({quantity} шт.)", show_alert=True)
    
    await callback.message.answer(f"✅ Товар '{product_name}' ({quantity} шт.) додано до кошика.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти до кошика 🛒", callback_data="show_cart")],
        [InlineKeyboardButton(text="Продовжити покупки 🛍️", callback_data="show_products")]
    ]))
    try: await callback.message.delete()
    except Exception: pass

@dp.callback_query(F.data == "show_cart")
async def show_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})

    if not cart:
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        return

    cart_text = "<b>🛒 Ваш кошик:</b>\n\n"
    total_sum = 0
    for item in cart.values():
        product = PRODUCTS[item['product_id']]
        cart_text += f"🔹 {product['name']} (x{item['quantity']}) - <b>{item['price']}$</b>\n"
        total_sum += item['price']
    
    cart_text += f"\n<b>Загальна сума: {total_sum:.2f}$</b>"
    
    await callback.message.edit_text(cart_text, parse_mode="HTML", reply_markup=get_cart_keyboard())

# --- БЛОК 10: ОБРОБНИКИ ОФОРМЛЕННЯ ЗАМОВЛЕННЯ (FSM) ---
@dp.callback_query(F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Для оформлення замовлення, будь ласка, вкажіть ваше <b>ПІБ:</b>", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_name)

@dp.message(OrderState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Дякую! Тепер введіть ваш <b>номер телефону:</b>", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_phone)

@dp.message(OrderState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Вкажіть ваше <b>місто:</b>", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_city)

@dp.message(OrderState.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Вкажіть <b>номер поштомату 'Нової Пошти':</b>", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_post)

@dp.message(OrderState.waiting_for_post)
async def process_post_office(message: types.Message, state: FSMContext):
    await state.update_data(post_office=message.text)
    user_data = await state.get_data()
    cart_items = user_carts.get(message.from_user.id, {})
    
    order_summary = "<b>✅ Перевірте ваше замовлення:</b>\n\n"
    order_summary += f"<b>ПІБ:</b> {user_data['name']}\n"
    order_summary += f"<b>Телефон:</b> {user_data['phone']}\n"
    order_summary += f"<b>Місто:</b> {user_data['city']}\n"
    order_summary += f"<b>Поштомат НП:</b> {user_data['post_office']}\n\n"
    
    order_summary += "<b>Товари:</b>\n"
    total_sum = 0
    for item in cart_items.values():
        product = PRODUCTS[item['product_id']]
        order_summary += f" - {product['name']} (x{item['quantity']}) - {item['price']}$\n"
        total_sum += item['price']
    order_summary += f"\n<b>🔥 Загальна сума: {total_sum:.2f}$</b>"
    
    await state.update_data(total_sum=total_sum)

    await message.answer(order_summary, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти до оплати 💸", callback_data="proceed_to_payment")]
    ]))


# --- БЛОК 11: ПОВНИЙ ФУНКЦІОНАЛ ОПЛАТИ ТА КЕРУВАННЯ ЗАМОВЛЕННЯМ ---

# --- Частина 1: Логіка для клієнта (вибір мережі та оплата) ---
PAYMENT_ADDRESSES = {"TRC20": "TLARjDwtn6xEs1cAzRSfLNrbBLLPTVwmqf", "ERC20": "0x8656f5bdec1917a3cee864c9eb74c6d53833e023"}

def get_payment_network_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="USDT (TRC20 - Tron)", callback_data="pay_network:TRC20")], [InlineKeyboardButton(text="USDT (ERC20 - Ethereum)", callback_data="pay_network:ERC20")]])

@dp.callback_query(F.data == "proceed_to_payment")
async def select_payment_network(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Будь ласка, оберіть зручну мережу для оплати:", reply_markup=get_payment_network_keyboard())
    await callback.answer()

# --- ЗМІНЕНО: Покращено вигляд повідомлення для оплати ---
@dp.callback_query(F.data.startswith("pay_network:"))
async def show_payment_details(callback: types.CallbackQuery, state: FSMContext):
    network = callback.data.split(":")[1]
    address = PAYMENT_ADDRESSES.get(network)
    user_data = await state.get_data()
    total_sum = user_data.get('total_sum', 0)
    
    payment_details = (
        f"<b>Для оплати перекажіть точну суму на гаманець.</b>\n\n"
        f"<b>Сума для переводу:</b>\n<code>{total_sum:.2f} USDT</code>\n\n"
        f"<b>Мережа:</b>\n<code>{network}</code>\n\n"
        f"<b>Гаманець</b> (натисніть на адресу, щоб скопіювати):\n<code>{address}</code>\n\n"
        f"Після успішної оплати, будь ласка, скопіюйте <b>ID (хеш) транзакції</b> та надішліть його наступним повідомленням у цей чат для підтвердження."
    )

    await callback.message.edit_text(payment_details, parse_mode="HTML", disable_web_page_preview=True)
    await state.set_state(OrderState.waiting_for_payment_confirmation)

# --- Частина 2: Створення замовлення в каналі ---
@dp.message(OrderState.waiting_for_payment_confirmation)
async def process_payment_confirmation(message: types.Message, state: FSMContext):
    global ORDER_COUNTER
    order_id = ORDER_COUNTER
    ORDER_COUNTER += 1

    await state.update_data(tx_id=message.text)
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    cart_items = user_carts.get(user_id, {})
    cart_description = ""
    for item in cart_items.values():
        product = PRODUCTS[item['product_id']]
        cart_description += f" - {product['name']} (x{item['quantity']}) - {item['price']}$\n"

    user_link = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"

    admin_message = (
        f"🔔 <b>Нове замовлення №{order_id} на підтвердження!</b>\n\n"
        f"<b>Клієнт:</b> {user_link} (ID: <code>{user_id}</code>)\n"
        f"<b>ПІБ:</b> {user_data.get('name', 'Не вказано')}\n"
        f"<b>Телефон:</b> {user_data.get('phone', 'Не вказано')}\n\n"
        f"<b>Доставка:</b>\n"
        f"<b>Місто:</b> {user_data.get('city', 'Не вказано')}\n"
        f"<b>Поштомат НП:</b> {user_data.get('post_office', 'Не вказано')}\n\n"
        f"<b>Товари:</b>\n{cart_description}"
        f"<b>🔥 Загальна сума: {user_data.get('total_sum', 0):.2f}$</b>\n\n"
        f"<b>Хеш транзакції (TxID):</b>\n<code>{user_data.get('tx_id', 'Немає')}</code>"
    )
    
    manager_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити оплату", callback_data=f"confirm_order:{user_id}:{order_id}")], 
        [InlineKeyboardButton(text="⚠️ Повідомити про проблему", callback_data=f"report_problem:{user_id}:{order_id}")]
    ])
    
    try:
        await bot.send_message(CHANNEL_ID, admin_message, parse_mode="HTML", reply_markup=manager_keyboard)
        await message.answer(f"✅ Дякуємо! Ваше замовлення №{order_id} прийнято в обробку. Ми перевіримо оплату та зв'яжемося з вами найближчим часом.")
        user_carts.pop(user_id, None)
        await state.clear()
    except Exception as e:
        logging.error(f"ПОМИЛКА при відправці в канал (ID: {CHANNEL_ID}): {e}")
        await message.answer("🔴 Виникла технічна помилка при оформленні замовлення. Будь ласка, зверніться до адміністратора.")

# --- Частина 3: Логіка для менеджера ---
@dp.callback_query(F.data.startswith("confirm_order:"))
async def handle_order_confirmation(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    customer_id = int(parts[1])
    order_id = int(parts[2])

    await bot.send_message(customer_id, f"✅ Вашу оплату за замовленням №{order_id} підтверджено! Очікуйте на номер ТТН для відстеження.")
    original_text = callback.message.text
    
    sent_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚚 Підтвердити відправку", callback_data=f"confirm_shipment:{customer_id}:{order_id}")]])
    await callback.message.edit_text(original_text + "\n\n<b>✅ ОПЛАТУ ПІДТВЕРДЖЕНО</b>", parse_mode="HTML", reply_markup=sent_keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_shipment:"))
async def ask_for_ttn(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    customer_id = int(parts[1])
    order_id = int(parts[2])

    prompt_message = await callback.message.reply(f"Будь ласка, надішліть номер ТТН для замовлення №{order_id} (клієнт ID: {customer_id}).")
    
    channel_context[CHANNEL_ID] = {
        "action": "wait_ttn",
        "customer_id": customer_id, 
        "order_id": order_id,
        "order_message_id": callback.message.message_id, 
        "original_text": callback.message.text,
        "prompt_message_id": prompt_message.message_id
    }
    await callback.answer()

@dp.callback_query(F.data.startswith("report_problem:"))
async def ask_for_problem(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    customer_id = int(parts[1])
    order_id = int(parts[2])

    prompt_message = await callback.message.reply(f"Будь ласка, надішліть опис проблеми по замовленню №{order_id} для клієнта (ID: {customer_id}).")

    channel_context[CHANNEL_ID] = {
        "action": "wait_problem",
        "customer_id": customer_id,
        "order_id": order_id,
        "prompt_message_id": prompt_message.message_id
    }
    await callback.answer()

@dp.channel_post(F.text)
async def process_channel_post(message: types.Message):
    if message.chat.id != CHANNEL_ID or CHANNEL_ID not in channel_context:
        return

    context = channel_context[CHANNEL_ID]
    
    if context.get("action") == "wait_ttn":
        tracking_number = message.text
        customer_id = context['customer_id']
        order_id = context['order_id']
        original_text = context['original_text']
        msg_id = context['order_message_id']
        prompt_message_id = context['prompt_message_id']

        await bot.send_message(customer_id, f"Ваше замовлення №{order_id} відправлено. ТТН №<b>{tracking_number}</b>", parse_mode="HTML")
        
        final_text = original_text + f"\n\n🚚 <b>ВІДПРАВЛЕНО</b>\n<b>ТТН:</b> <code>{tracking_number}</code>"
        await bot.edit_message_text(final_text, chat_id=CHANNEL_ID, message_id=msg_id, parse_mode="HTML")
        
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=prompt_message_id)
            await message.delete()
        except Exception as e:
            logging.error(f"Не вдалося видалити повідомлення: {e}")

        del channel_context[CHANNEL_ID]

    elif context.get("action") == "wait_problem":
        problem_text = message.text
        customer_id = context['customer_id']
        order_id = context['order_id']
        prompt_message_id = context['prompt_message_id']
        
        await bot.send_message(customer_id, f"<b>🔔 Повідомлення від менеджера щодо вашого замовлення №{order_id}:</b>\n\n<i>«{problem_text}»</i>", parse_mode="HTML")
        
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=prompt_message_id)
            await message.delete()
        except Exception as e:
            logging.error(f"Не вдалося видалити повідомлення про проблему: {e}")
        
        del channel_context[CHANNEL_ID]


# --- БЛОК 12: ЗАПУСК БОТА НА СЕРВЕРІ (WEBHOOK РЕЖИМ) ---
async def on_startup(bot: Bot):
    # Встановлюємо вебхук один раз при старті
    webhook_url = f"{WEB_SERVER_HOST}/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set to {webhook_url}")

async def main():
    dp.startup.register(on_startup)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=f"/{BOT_TOKEN}")

    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=WEB_SERVER_PORT)
    await site.start()
    
    logging.info(f"Bot started on port {WEB_SERVER_PORT}!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())