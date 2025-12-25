import telebot
from telebot import types
from datetime import datetime

from database import db
from config import TOKEN

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ===================== HELPERS عمومی =====================

def get_user_row(user_id):
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    return cur.fetchone()

def get_role(user_id):
    row = get_user_row(user_id)
    if row:
        return row[1]
    return None

def upsert_user(user):
    telegram_id = user.id
    username = user.username or ""
    existing = get_user_row(telegram_id)
    cur = db.cursor()

    if existing:
        cur.execute(
            "UPDATE users SET username=? WHERE telegram_id=?",
            (username, telegram_id)
        )
    else:
        cur.execute(
            "INSERT INTO users (telegram_id, role, username) VALUES (?, ?, ?)",
            (telegram_id, None, username)
        )
    db.commit()

def set_role(user_id, role):
    row = get_user_row(user_id)
    cur = db.cursor()
    if row:
        cur.execute(
            "UPDATE users SET role=? WHERE telegram_id=?",
            (role, user_id)
        )
    else:
        cur.execute(
            "INSERT INTO users (telegram_id, role) VALUES (?, ?)",
            (user_id, role)
        )
    db.commit()

def get_seller_profile(user_id):
    cur = db.cursor()
    cur.execute(
        "SELECT username, profile_photo, shop_name, bio, phone FROM users WHERE telegram_id=?",
        (user_id,)
    )
    return cur.fetchone()

def count_seller_products(user_id):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM products WHERE seller_id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

# ===================== HELPERS ادمین =====================

def is_admin(user_id):
    cur = db.cursor()
    cur.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

def add_admin(user_id):
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    db.commit()

def remove_admin(user_id):
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    db.commit()

# ===================== KEYBOARDS =====================

def seller_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👤 پروفایل من")
    kb.add("➕ ثبت محصول", "📦 محصولات من")
    kb.add("🛍 مشاهده همه محصولات")
    return kb

def buyer_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛍 مشاهده همه محصولات")
    kb.add("⭐ برای بعداً", "🛒 سبد خرید")
    kb.add("📜 تاریخچه")
    return kb

def admin_keyboard_base():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 مدیریت کاربران", "🛍 مدیریت محصولات")
    kb.add("➕ افزودن ادمین", "❌ حذف ادمین")
    kb.add("🚫 بن کاربر", "🔄 تغییر نقش کاربر")
    kb.add("🗑 حذف محصول", "✏️ ویرایش محصول")
    return kb

def merged_keyboard_for_user(user_id):
    role = get_role(user_id)
    if role == "seller":
        base = seller_keyboard()
    else:
        base = buyer_keyboard()

    if not is_admin(user_id):
        return base

    # ادغام کیبورد نقش + امکانات ادمین
    admin_row1 = ["👥 مدیریت کاربران", "🛍 مدیریت محصولات"]
    admin_row2 = ["➕ افزودن ادمین", "❌ حذف ادمین"]
    admin_row3 = ["🚫 بن کاربر", "🔄 تغییر نقش کاربر"]
    admin_row4 = ["🗑 حذف محصول", "✏️ ویرایش محصول"]

    for row in [admin_row1, admin_row2, admin_row3, admin_row4]:
        base.row(*row)
    return base

# ===================== START =====================

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    upsert_user(user)

    # برای راحتی: هرکس /make_me_admin را یک‌بار بزند، ادمین می‌شود (در محیط خودت استفاده کن)
    # می‌تونی بعداً این را حذف کنی یا محدودش کنی.

    role = get_role(user.id)
    if role is None:
        ask_role(message)
    else:
        send_main_menu(message, role)

@bot.message_handler(commands=['make_me_admin'])
def make_me_admin(message):
    add_admin(message.from_user.id)
    bot.send_message(message.chat.id, "تو الان ادمین شدی ✔️", reply_markup=merged_keyboard_for_user(message.from_user.id))

# ===================== ROLE SELECT =====================

def ask_role(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🛒 خریدار", callback_data="role_buyer"),
        types.InlineKeyboardButton("🛍 فروشنده", callback_data="role_seller")
    )
    bot.send_message(message.chat.id, "نقشت رو انتخاب کن:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("role_"))
def set_user_role(call):
    role = call.data.split("_")[1]
    set_role(call.from_user.id, role)

    bot.edit_message_text(
        "نقش با موفقیت ثبت شد ✔️",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

    fake_msg = call.message
    fake_msg.from_user = call.from_user
    send_main_menu(fake_msg, role)

# ===================== MAIN MENU =====================

def send_main_menu(message, role=None):
    user_id = message.from_user.id
    kb = merged_keyboard_for_user(user_id)
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=kb)

# ===================== PROFILE (SELLER ONLY) =====================

@bot.message_handler(func=lambda m: m.text == "👤 پروفایل من")
def show_profile(message):
    user_id = message.from_user.id
    role = get_role(user_id)
    if role != "seller":
        bot.send_message(message.chat.id, "این بخش فقط برای فروشنده‌هاست.")
        return

    profile = get_seller_profile(user_id)
    username, photo, shop_name, bio, phone = profile

    if not photo:
        msg = bot.send_message(
            message.chat.id,
            "هنوز پروفایل نداری.\nاول یک عکس پروفایل بفرست:"
        )
        bot.register_next_step_handler(msg, set_profile_photo_first_time)
        return

    count = count_seller_products(user_id)

    caption_lines = []
    if shop_name:
        caption_lines.append(f"*{shop_name}*")
    else:
        caption_lines.append("*بدون نام فروشگاه*")

    if username:
        caption_lines.append(f"👤 @{username}")
    else:
        caption_lines.append("👤 بدون یوزرنیم")

    if bio:
        caption_lines.append(f"📝 {bio}")

    if phone:
        caption_lines.append(f"📞 {phone}")

    caption_lines.append(f"📦 تعداد محصولات: {count}")

    caption = "\n".join(caption_lines)

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("تغییر عکس پروفایل", callback_data="change_profile_photo"),
        types.InlineKeyboardButton("ویرایش اطلاعات", callback_data="edit_profile_info")
    )

    bot.send_photo(
        message.chat.id,
        photo,
        caption=caption,
        reply_markup=kb
    )

def set_profile_photo_first_time(message):
    if not message.photo:
        bot.send_message(message.chat.id, "لطفاً یک عکس بفرست.")
        msg = bot.send_message(message.chat.id, "دوباره تلاش کن، عکس پروفایل را بفرست:")
        bot.register_next_step_handler(msg, set_profile_photo_first_time)
        return

    file_id = message.photo[-1].file_id
    user_id = message.from_user.id

    cur = db.cursor()
    cur.execute(
        "UPDATE users SET profile_photo=? WHERE telegram_id=?",
        (file_id, user_id)
    )
    db.commit()

    msg = bot.send_message(message.chat.id, "نام فروشگاه را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, set_profile_shop_name)

def set_profile_shop_name(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET shop_name=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    msg = bot.send_message(message.chat.id, "بیو (توضیحات پروفایل) را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, set_profile_bio)

def set_profile_bio(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET bio=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    msg = bot.send_message(message.chat.id, "شماره تماس را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, set_profile_phone)

def set_profile_phone(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET phone=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    bot.send_message(message.chat.id, "پروفایل با موفقیت ساخته شد ✔️")
    show_profile(message)

@bot.callback_query_handler(func=lambda c: c.data == "change_profile_photo")
def change_profile_photo(call):
    msg = bot.send_message(call.message.chat.id, "عکس جدید پروفایل را بفرست:")
    bot.register_next_step_handler(msg, set_new_profile_photo)

def set_new_profile_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "لطفاً یک عکس بفرست.")
        msg = bot.send_message(message.chat.id, "دوباره تلاش کن، عکس پروفایل را بفرست:")
        bot.register_next_step_handler(msg, set_new_profile_photo)
        return

    file_id = message.photo[-1].file_id
    user_id = message.from_user.id

    cur = db.cursor()
    cur.execute(
        "UPDATE users SET profile_photo=? WHERE telegram_id=?",
        (file_id, user_id)
    )
    db.commit()

    bot.send_message(message.chat.id, "عکس پروفایل با موفقیت تغییر کرد ✔️")
    show_profile(message)

@bot.callback_query_handler(func=lambda c: c.data == "edit_profile_info")
def edit_profile_info(call):
    msg = bot.send_message(call.message.chat.id, "نام جدید فروشگاه را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, edit_profile_shop_name)

def edit_profile_shop_name(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET shop_name=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    msg = bot.send_message(message.chat.id, "بیو جدید را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, edit_profile_bio)

def edit_profile_bio(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET bio=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    msg = bot.send_message(message.chat.id, "شماره تماس جدید را وارد کن (یا بنویس رد):")
    bot.register_next_step_handler(msg, edit_profile_phone)

def edit_profile_phone(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cur = db.cursor()
    if text.lower() != "رد":
        cur.execute(
            "UPDATE users SET phone=? WHERE telegram_id=?",
            (text, user_id)
        )
        db.commit()

    bot.send_message(message.chat.id, "اطلاعات پروفایل با موفقیت به‌روزرسانی شد ✔️")
    show_profile(message)

# ===================== SELLER: ADD PRODUCT =====================

@bot.message_handler(func=lambda m: m.text == "➕ ثبت محصول")
def add_product(message):
    role = get_role(message.from_user.id)
    if role != "seller":
        bot.send_message(message.chat.id, "این بخش فقط برای فروشنده‌هاست.")
        return

    msg = bot.send_message(message.chat.id, "عنوان محصول:")
    bot.register_next_step_handler(msg, get_product_title)

def get_product_title(message):
    title = message.text.strip()
    if not title:
        msg = bot.send_message(message.chat.id, "عنوان نامعتبر است، دوباره وارد کن:")
        bot.register_next_step_handler(msg, get_product_title)
        return

    msg = bot.send_message(message.chat.id, "توضیحات محصول:")
    bot.register_next_step_handler(msg, get_product_description, title)

def get_product_description(message, title):
    desc = message.text.strip()
    msg = bot.send_message(message.chat.id, "قیمت محصول (عدد):")
    bot.register_next_step_handler(msg, get_product_price, title, desc)

def get_product_price(message, title, desc):
    try:
        price = int(message.text.strip())
    except:
        msg = bot.send_message(message.chat.id, "قیمت نامعتبر است، یک عدد بفرست:")
        bot.register_next_step_handler(msg, get_product_price, title, desc)
        return

    msg = bot.send_message(message.chat.id, "عکس محصول را بفرست:")
    bot.register_next_step_handler(msg, get_product_photo, title, desc, price)

def get_product_photo(message, title, desc, price):
    if not message.photo:
        msg = bot.send_message(message.chat.id, "لطفاً یک عکس بفرست:")
        bot.register_next_step_handler(msg, get_product_photo, title, desc, price)
        return

    file_id = message.photo[-1].file_id
    seller_id = message.from_user.id

    cur = db.cursor()
    cur.execute(
        "INSERT INTO products (seller_id, title, description, price, photo) VALUES (?, ?, ?, ?, ?)",
        (seller_id, title, desc, price, file_id)
    )
    db.commit()

    bot.send_message(message.chat.id, "محصول با موفقیت ثبت شد ✔️")

# ===================== SELLER: MY PRODUCTS =====================

@bot.message_handler(func=lambda m: m.text == "📦 محصولات من")
def my_products(message):
    user_id = message.from_user.id
    role = get_role(user_id)
    if role != "seller":
        bot.send_message(message.chat.id, "این بخش فقط برای فروشنده‌هاست.")
        return

    cur = db.cursor()
    cur.execute(
        "SELECT id, title, description, price, photo FROM products WHERE seller_id=?",
        (user_id,)
    )
    products = cur.fetchall()

    if not products:
        bot.send_message(message.chat.id, "هنوز هیچ محصولی ثبت نکردی.")
        return

    for pid, title, desc, price, photo in products:
        caption = f"*{title}*\n{desc}\n💰 قیمت: {price} تومان\n🆔 محصول: {pid}"

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_{pid}"),
            types.InlineKeyboardButton("❌ حذف", callback_data=f"delete_{pid}")
        )

        bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb)

# ===================== DELETE PRODUCT (seller/admin) =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("delete_"))
def delete_product(call):
    pid = call.data.split("_")[1]

    cur = db.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()

    bot.answer_callback_query(call.id, "محصول حذف شد ✔️")
    try:
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption="❌ این محصول حذف شد."
        )
    except:
        pass

# ===================== EDIT PRODUCT MENU =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_") and not any(
    c.data.startswith(x) for x in ["edit_title_", "edit_desc_", "edit_price_", "edit_photo_"]
))
def edit_product_menu(call):
    pid = call.data.split("_")[1]

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✏️ تغییر عنوان", callback_data=f"edit_title_{pid}"),
        types.InlineKeyboardButton("📝 تغییر توضیحات", callback_data=f"edit_desc_{pid}")
    )
    kb.add(
        types.InlineKeyboardButton("💰 تغییر قیمت", callback_data=f"edit_price_{pid}"),
        types.InlineKeyboardButton("🖼 تغییر عکس", callback_data=f"edit_photo_{pid}")
    )

    bot.send_message(call.message.chat.id, "چه چیزی را می‌خوای ویرایش کنی:", reply_markup=kb)

# ===================== EDIT TITLE =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_title_"))
def edit_title(call):
    pid = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "عنوان جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_title, pid)

def save_new_title(message, pid):
    new_title = message.text.strip()
    cur = db.cursor()
    cur.execute("UPDATE products SET title=? WHERE id=?", (new_title, pid))
    db.commit()
    bot.send_message(message.chat.id, "عنوان با موفقیت تغییر کرد ✔️")

# ===================== EDIT DESCRIPTION =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_desc_"))
def edit_desc(call):
    pid = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "توضیحات جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_desc, pid)

def save_new_desc(message, pid):
    new_desc = message.text.strip()
    cur = db.cursor()
    cur.execute("UPDATE products SET description=? WHERE id=?", (new_desc, pid))
    db.commit()
    bot.send_message(message.chat.id, "توضیحات با موفقیت تغییر کرد ✔️")

# ===================== EDIT PRICE =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_price_"))
def edit_price(call):
    pid = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "قیمت جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_price, pid)

def save_new_price(message, pid):
    try:
        new_price = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "قیمت نامعتبر است.")
        return

    cur = db.cursor()
    cur.execute("UPDATE products SET price=? WHERE id=?", (new_price, pid))
    db.commit()
    bot.send_message(message.chat.id, "قیمت با موفقیت تغییر کرد ✔️")

# ===================== EDIT PHOTO =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_photo_"))
def edit_photo(call):
    pid = call.data.split("_")[2]
    msg = bot.send_message(call.message.chat.id, "عکس جدید محصول را بفرست:")
    bot.register_next_step_handler(msg, save_new_photo, pid)

def save_new_photo(message, pid):
    if not message.photo:
        bot.send_message(message.chat.id, "لطفاً یک عکس بفرست.")
        return

    new_photo = message.photo[-1].file_id
    cur = db.cursor()
    cur.execute("UPDATE products SET photo=? WHERE id=?", (new_photo, pid))
    db.commit()

    bot.send_message(message.chat.id, "عکس محصول با موفقیت تغییر کرد ✔️")

# ===================== BUYER: SHOW ALL PRODUCTS =====================

@bot.message_handler(func=lambda m: m.text in ["🛍 مشاهده محصولات", "🛍 مشاهده همه محصولات"])
def show_all_products(message):
    cur = db.cursor()
    cur.execute(
        "SELECT p.id, p.title, p.description, p.price, p.photo, p.seller_id, u.username \
         FROM products p LEFT JOIN users u ON p.seller_id = u.telegram_id"
    )
    products = cur.fetchall()

    if not products:
        bot.send_message(message.chat.id, "هیچ محصولی ثبت نشده.")
        return

    for pid, title, desc, price, photo, seller_id, username in products:
        seller_line = ""
        if username:
            seller_line = f"\n👤 فروشنده: @{username}"
        caption = f"*{title}*\n{desc}\n💰 قیمت: {price} تومان{seller_line}"

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("⭐ برای بعداً", callback_data=f"later_add_{pid}"),
            types.InlineKeyboardButton("🛒 افزودن به سبد", callback_data=f"cart_add_{pid}")
        )

        bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb)

# ===================== LATER: ADD =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("later_add_"))
def later_add(call):
    user_id = call.from_user.id
    product_id = int(call.data.split("_")[2])

    cur = db.cursor()
    cur.execute("SELECT id FROM later WHERE user_id=? AND product_id=?", (user_id, product_id))
    if not cur.fetchone():
        cur.execute("INSERT INTO later (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        db.commit()

    bot.answer_callback_query(call.id, "به لیست برای بعداً اضافه شد ✔️")

# ===================== CART: ADD =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_add_"))
def cart_add(call):
    user_id = call.from_user.id
    product_id = int(call.data.split("_")[2])

    cur = db.cursor()
    cur.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    db.commit()

    bot.answer_callback_query(call.id, "به سبد خرید اضافه شد ✔️")

# ===================== LATER: LIST =====================

@bot.message_handler(func=lambda m: m.text == "⭐ برای بعداً")
def show_later(message):
    user_id = message.from_user.id
    cur = db.cursor()
    cur.execute(
        "SELECT l.id, p.id, p.title, p.description, p.price, p.photo \
         FROM later l JOIN products p ON l.product_id = p.id \
         WHERE l.user_id=?",
        (user_id,)
    )
    rows = cur.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "لیست برای بعداً خالی است.")
        return

    for later_id, pid, title, desc, price, photo in rows:
        caption = f"*{title}*\n{desc}\n💰 قیمت: {price} تومان"

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("❌ حذف از برای بعداً", callback_data=f"later_del_{later_id}"),
            types.InlineKeyboardButton("🛒 افزودن به سبد", callback_data=f"later_to_cart_{later_id}")
        )

        bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("later_del_"))
def later_delete(call):
    later_id = int(call.data.split("_")[2])
    cur = db.cursor()
    cur.execute("DELETE FROM later WHERE id=?", (later_id,))
    db.commit()
    bot.answer_callback_query(call.id, "از لیست برای بعداً حذف شد ✔️")

@bot.callback_query_handler(func=lambda c: c.data.startswith("later_to_cart_"))
def later_to_cart(call):
    later_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    cur = db.cursor()
    cur.execute("SELECT product_id FROM later WHERE id=?", (later_id,))
    row = cur.fetchone()
    if not row:
        bot.answer_callback_query(call.id, "این آیتم دیگر در لیست برای بعداً نیست.")
        return

    product_id = row[0]
    cur.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    db.commit()

    bot.answer_callback_query(call.id, "به سبد خرید اضافه شد ✔️")

# ===================== CART: LIST =====================

@bot.message_handler(func=lambda m: m.text == "🛒 سبد خرید")
def show_cart(message):
    user_id = message.from_user.id
    cur = db.cursor()
    cur.execute(
        "SELECT c.id, p.id, p.title, p.description, p.price, p.photo, p.seller_id, u.username \
         FROM cart c \
         JOIN products p ON c.product_id = p.id \
         LEFT JOIN users u ON p.seller_id = u.telegram_id \
         WHERE c.user_id=?",
        (user_id,)
    )
    rows = cur.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "سبد خرید خالی است.")
        return

    total = 0
    for cart_id, pid, title, desc, price, photo, seller_id, username in rows:
        total += price
        seller_line = ""
        if username:
            seller_line = f"\n👤 فروشنده: @{username}"
        caption = f"*{title}*\n{desc}\n💰 قیمت: {price} تومان{seller_line}"

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("📩 پیام به فروشنده", callback_data=f"contact_{pid}")
        )

        bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb)

    bot.send_message(message.chat.id, f"💰 مجموع سبد خرید: {total} تومان")

# ===================== CONTACT SELLER (HISTORY) =====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("contact_"))
def contact_seller(call):
    user_id = call.from_user.id
    product_id = int(call.data.split("_")[1])

    cur = db.cursor()
    cur.execute(
        "SELECT p.seller_id, u.username \
         FROM products p LEFT JOIN users u ON p.seller_id = u.telegram_id \
         WHERE p.id=?",
        (product_id,)
    )
    row = cur.fetchone()
    if not row:
        bot.answer_callback_query(call.id, "محصول پیدا نشد.")
        return

    seller_id, username = row

    timestamp = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO history (user_id, product_id, seller_id, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, product_id, seller_id, timestamp)
    )
    db.commit()

    bot.answer_callback_query(call.id, "در تاریخچه ثبت شد ✔️")

    if username:
        link = f"https://t.me/{username}"
        bot.send_message(
            call.message.chat.id,
            f"برای پیام دادن به فروشنده روی لینک زیر بزن:\n{link}"
        )
    else:
        bot.send_message(
            call.message.chat.id,
            "این فروشنده یوزرنیم ندارد. نمی‌توان لینک مستقیم ساخت."
        )

# ===================== HISTORY LIST =====================

@bot.message_handler(func=lambda m: m.text == "📜 تاریخچه")
def show_history(message):
    user_id = message.from_user.id
    cur = db.cursor()
    cur.execute(
        "SELECT h.timestamp, p.title, u.username \
         FROM history h \
         JOIN products p ON h.product_id = p.id \
         LEFT JOIN users u ON h.seller_id = u.telegram_id \
         WHERE h.user_id=? \
         ORDER BY h.id DESC \
         LIMIT 20",
        (user_id,)
    )
    rows = cur.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "هنوز هیچ پیامی به فروشنده‌ها ثبت نشده.")
        return

    lines = ["📜 آخرین پیام‌ها به فروشنده‌ها:"]
    for ts, title, username in rows:
        time_str = ts.replace("T", " ").split(".")[0]
        seller_part = f"@{username}" if username else "بدون یوزرنیم"
        lines.append(f"- {time_str} | {title} | {seller_part}")

    bot.send_message(message.chat.id, "\n".join(lines))

# ===================== ADMIN FEATURES =====================

@bot.message_handler(func=lambda m: m.text == "➕ افزودن ادمین")
def ask_new_admin(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی عددی کاربر را بفرست:")
    bot.register_next_step_handler(msg, save_new_admin)

def save_new_admin(message):
    try:
        uid = int(message.text.strip())
        add_admin(uid)
        bot.send_message(message.chat.id, "ادمین جدید اضافه شد ✔️")
    except:
        bot.send_message(message.chat.id, "آیدی نامعتبر است.")

@bot.message_handler(func=lambda m: m.text == "❌ حذف ادمین")
def ask_remove_admin(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی ادمین را بفرست:")
    bot.register_next_step_handler(msg, remove_admin_handler)

def remove_admin_handler(message):
    try:
        uid = int(message.text.strip())
        remove_admin(uid)
        bot.send_message(message.chat.id, "ادمین حذف شد ✔️")
    except:
        bot.send_message(message.chat.id, "آیدی نامعتبر است.")

@bot.message_handler(func=lambda m: m.text == "🚫 بن کاربر")
def ask_ban_user(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی کاربر را بفرست:")
    bot.register_next_step_handler(msg, ban_user_handler)

def ban_user_handler(message):
    try:
        uid = int(message.text.strip())
        cur = db.cursor()
        cur.execute("DELETE FROM users WHERE telegram_id=?", (uid,))
        db.commit()
        bot.send_message(message.chat.id, "کاربر بن شد ✔️")
    except:
        bot.send_message(message.chat.id, "آیدی نامعتبر است.")

@bot.message_handler(func=lambda m: m.text == "🔄 تغییر نقش کاربر")
def ask_change_role(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی کاربر را بفرست:")
    bot.register_next_step_handler(msg, change_role_step2)

def change_role_step2(message):
    try:
        uid = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "آیدی نامعتبر است.")
        return
    msg = bot.send_message(message.chat.id, "نقش جدید را وارد کن (buyer/seller):")
    bot.register_next_step_handler(msg, change_role_final, uid)

def change_role_final(message, uid):
    role = message.text.strip()
    if role not in ["buyer", "seller"]:
        bot.send_message(message.chat.id, "نقش نامعتبر است.")
        return
    cur = db.cursor()
    cur.execute("UPDATE users SET role=? WHERE telegram_id=?", (role, uid))
    db.commit()
    bot.send_message(message.chat.id, "نقش کاربر تغییر کرد ✔️")

@bot.message_handler(func=lambda m: m.text == "🗑 حذف محصول")
def ask_delete_product_admin(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی محصول را بفرست:")
    bot.register_next_step_handler(msg, delete_product_admin)

def delete_product_admin(message):
    try:
        pid = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "آیدی محصول نامعتبر است.")
        return
    cur = db.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    bot.send_message(message.chat.id, "محصول حذف شد ✔️")

@bot.message_handler(func=lambda m: m.text == "✏️ ویرایش محصول")
def ask_edit_product_admin(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "آیدی محصول را بفرست:")
    bot.register_next_step_handler(msg, edit_product_admin_step2)

def edit_product_admin_step2(message):
    try:
        pid = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "آیدی محصول نامعتبر است.")
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✏️ عنوان", callback_data=f"admin_edit_title_{pid}"),
        types.InlineKeyboardButton("📝 توضیحات", callback_data=f"admin_edit_desc_{pid}")
    )
    kb.add(
        types.InlineKeyboardButton("💰 قیمت", callback_data=f"admin_edit_price_{pid}"),
        types.InlineKeyboardButton("🖼 عکس", callback_data=f"admin_edit_photo_{pid}")
    )
    bot.send_message(message.chat.id, "چه چیزی را می‌خوای ویرایش کنی:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_edit_title_"))
def admin_edit_title(call):
    pid = int(call.data.split("_")[-1])
    msg = bot.send_message(call.message.chat.id, "عنوان جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_title, pid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_edit_desc_"))
def admin_edit_desc(call):
    pid = int(call.data.split("_")[-1])
    msg = bot.send_message(call.message.chat.id, "توضیحات جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_desc, pid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_edit_price_"))
def admin_edit_price(call):
    pid = int(call.data.split("_")[-1])
    msg = bot.send_message(call.message.chat.id, "قیمت جدید را وارد کن:")
    bot.register_next_step_handler(msg, save_new_price, pid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_edit_photo_"))
def admin_edit_photo(call):
    pid = int(call.data.split("_")[-1])
    msg = bot.send_message(call.message.chat.id, "عکس جدید محصول را بفرست:")
    bot.register_next_step_handler(msg, save_new_photo, pid)

# ===================== CATCH-ALL برای غیر ادمین =====================

@bot.message_handler(func=lambda m: True)
def catch_all(message):
    user_id = message.from_user.id
    # اگر ادمین است، مزاحمش نشیم (پیام می‌تونه برای مدیریت استفاده شود)
    if is_admin(user_id):
        return
    # اگر غیر از کامندها چیزی زد، همون پیام رو براش برگردون
    if not message.text.startswith("/"):
        bot.send_message(message.chat.id, f"پیام شما:\n{message.text}")

# ===================== RUN =====================

print("Bot is running...")
bot.infinity_polling()
