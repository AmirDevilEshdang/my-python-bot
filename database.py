import sqlite3
from config import DB_NAME

def connect_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

db = connect_db()

def create_tables():
    cur = db.cursor()

    # جدول کاربران
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        role TEXT,
        username TEXT,
        profile_photo TEXT,
        shop_name TEXT,
        bio TEXT,
        phone TEXT
    )
    """)

    # جدول محصولات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        title TEXT,
        description TEXT,
        price INTEGER,
        photo TEXT
    )
    """)

    # جدول برای بعداً
    cur.execute("""
    CREATE TABLE IF NOT EXISTS later (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER
    )
    """)

    # جدول سبد خرید
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER
    )
    """)

    # جدول تاریخچه پیام به فروشنده
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        seller_id INTEGER,
        timestamp TEXT
    )
    """)

    # جدول ادمین‌ها
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )
    """)

    db.commit()
    print("Tables created successfully!")

create_tables()
