# database.py
import sqlite3
import json
import random
import string
from datetime import datetime

DB_NAME = "shop.db"

def init_db():
    """Создаёт таблицы, если их ещё нет"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_visit TIMESTAMP
        )
    """)
    
    # Таблица категорий
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            icon TEXT DEFAULT '📁',
            is_hidden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица товаров
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            description TEXT,
            price_stars INTEGER,
            price_ton REAL,
            type TEXT,
            preview_image TEXT,
            in_stock INTEGER DEFAULT 1,
            sold_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    """)
    
    # Таблица для множественных фото цифровых товаров
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            file_id TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    
    # Таблица заказов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            tracking_number TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            payment_method TEXT,
            payment_details TEXT,
            delivery_address TEXT,
            tracking_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    
    # Таблица для сообщений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            file_id TEXT,
            reply TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Таблица для статистики посещений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            visit_date DATE,
            visit_time TIME,
            action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()

# ----- Пользователи -----

def add_user(telegram_id, username, full_name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, full_name, registered_at, last_visit)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (telegram_id, username, full_name))
    if cur.rowcount == 0:
        cur.execute("UPDATE users SET last_visit = CURRENT_TIMESTAMP WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cur.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username, full_name, registered_at, last_visit FROM users ORDER BY last_visit DESC")
    users = cur.fetchall()
    conn.close()
    return users

def get_top_buyers(limit=10):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.username, u.full_name, COUNT(o.id) as orders_count,
               SUM(CASE WHEN o.payment_method='stars' THEN p.price_stars ELSE p.price_ton END) as total_spent
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        WHERE o.status = 'paid'
        GROUP BY u.id
        ORDER BY total_spent DESC
        LIMIT ?
    """, (limit,))
    buyers = cur.fetchall()
    conn.close()
    return buyers

# ----- Категории -----

def add_category(name, description="", icon="📁", is_hidden=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO categories (name, description, icon, is_hidden)
            VALUES (?, ?, ?, ?)
        """, (name, description, icon, is_hidden))
        cat_id = cur.lastrowid
        conn.commit()
        return cat_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_all_categories(show_hidden=True):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if show_hidden:
        cur.execute("SELECT id, name, description, icon FROM categories ORDER BY name")
    else:
        cur.execute("SELECT id, name, description, icon FROM categories WHERE is_hidden=0 ORDER BY name")
    cats = cur.fetchall()
    conn.close()
    return cats

def get_category(category_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, icon FROM categories WHERE id = ?", (category_id,))
    cat = cur.fetchone()
    conn.close()
    return cat

def update_category(category_id, name, description, icon):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE categories SET name=?, description=?, icon=? WHERE id=?", (name, description, icon, category_id))
    conn.commit()
    conn.close()

def delete_category(category_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

def get_category_stats(category_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count

# ----- Товары -----

def add_product(category_id, name, description, price_stars, price_ton, product_type, preview_image=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (category_id, name, description, price_stars, price_ton, type, preview_image, in_stock)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (category_id, name, description, price_stars, price_ton, product_type, preview_image))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def add_product_image(product_id, file_id, sort_order=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO product_images (product_id, file_id, sort_order) VALUES (?, ?, ?)",
                (product_id, file_id, sort_order))
    img_id = cur.lastrowid
    conn.commit()
    conn.close()
    return img_id

def get_product_images(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, file_id, sort_order FROM product_images WHERE product_id=? ORDER BY sort_order", (product_id,))
    images = cur.fetchall()
    conn.close()
    return images

def get_products_by_category_and_type(category_id, product_type, in_stock_only=True):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if in_stock_only:
        cur.execute("""
            SELECT id, name, description, price_stars, price_ton, type, preview_image
            FROM products
            WHERE category_id=? AND type=? AND in_stock=1
            ORDER BY name
        """, (category_id, product_type))
    else:
        cur.execute("""
            SELECT id, name, description, price_stars, price_ton, type, preview_image
            FROM products
            WHERE category_id=? AND type=?
            ORDER BY name
        """, (category_id, product_type))
    prods = cur.fetchall()
    conn.close()
    return prods

def get_all_products():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.description, p.price_stars, p.price_ton, p.type,
               p.preview_image, p.in_stock, p.sold_count,
               c.id as cat_id, c.name as cat_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY c.name, p.name
    """)
    prods = cur.fetchall()
    conn.close()
    return prods

def get_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.description, p.price_stars, p.price_ton, p.type,
               p.preview_image, p.in_stock, p.sold_count,
               c.id as cat_id, c.name as cat_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    """, (product_id,))
    prod = cur.fetchone()
    conn.close()
    return prod

def delete_product(product_id):
    """Удалить товар по ID (каскадно удалятся и его изображения из-за ON DELETE CASCADE)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def mark_product_sold_out(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE products SET in_stock=0, sold_count=sold_count+1 WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

def check_product_available(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT in_stock FROM products WHERE id=?", (product_id,))
    res = cur.fetchone()
    conn.close()
    return res and res[0] == 1

# ----- Заказы -----

def generate_tracking_number():
    timestamp = datetime.now().strftime("%y%m%d")
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{rand}"

def create_order(user_id, product_id, payment_method, payment_details=None, delivery_address=None):
    tracking = generate_tracking_number()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, product_id, tracking_number, payment_method, payment_details, delivery_address, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (user_id, product_id, tracking, payment_method,
          json.dumps(payment_details) if payment_details else None,
          delivery_address))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id, tracking

def update_order_status(order_id, status, payment_details=None, tracking_info=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, order_id))
    if payment_details:
        cur.execute("UPDATE orders SET payment_details=? WHERE id=?", (json.dumps(payment_details), order_id))
    if tracking_info:
        cur.execute("UPDATE orders SET tracking_info=? WHERE id=?", (tracking_info, order_id))
    conn.commit()
    conn.close()

def get_order_by_tracking(tracking_number):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.*, u.username, u.full_name, p.name as product_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE o.tracking_number = ?
    """, (tracking_number,))
    order = cur.fetchone()
    conn.close()
    return order

def get_physical_orders(status=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT o.*, u.username, u.full_name, p.name as product_name
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            WHERE p.type='physical' AND o.status=?
            ORDER BY o.created_at DESC
        """, (status,))
    else:
        cur.execute("""
            SELECT o.*, u.username, u.full_name, p.name as product_name
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            WHERE p.type='physical'
            ORDER BY o.created_at DESC
        """)
    orders = cur.fetchall()
    conn.close()
    return orders

# ----- Сообщения -----

def add_message(user_id, message_text, file_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (user_id, message, file_id, status) VALUES (?, ?, ?, 'new')",
                (user_id, message_text, file_id))
    msg_id = cur.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def get_new_messages():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, u.username, u.full_name
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.status='new'
        ORDER BY m.created_at DESC
    """)
    msgs = cur.fetchall()
    conn.close()
    return msgs

def reply_to_message(message_id, reply_text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE messages SET reply=?, status='replied' WHERE id=?", (reply_text, message_id))
    conn.commit()
    conn.close()

# ----- Статистика -----

def add_visit(user_id, action):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO visits (user_id, visit_date, visit_time, action) VALUES (?, date('now'), time('now'), ?)",
                (user_id, action))
    conn.commit()
    conn.close()

def get_sales_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            SUM(CASE WHEN o.payment_method='stars' THEN p.price_stars ELSE 0 END) as total_stars,
            SUM(CASE WHEN o.payment_method='ton' THEN p.price_ton ELSE 0 END) as total_ton,
            COUNT(*) as total_orders,
            SUM(CASE WHEN o.status='paid' THEN 1 ELSE 0 END) as paid_orders
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.status = 'paid'
    """)
    stats = cur.fetchone()
    conn.close()
    return stats

def get_visitors_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM visits WHERE visit_date = date('now')")
    today_visitors = cur.fetchone()[0]
    cur.execute("SELECT visit_date, COUNT(DISTINCT user_id) FROM visits GROUP BY visit_date ORDER BY visit_date DESC LIMIT 30")
    daily = cur.fetchall()
    conn.close()
    return total_users, today_visitors, daily

def get_detailed_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    stats = {}
    cur.execute("SELECT COUNT(*) FROM users"); stats['total_users'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products"); stats['total_products'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products WHERE type='physical' AND in_stock=1"); stats['physical_available'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products WHERE type='digital'"); stats['digital_total'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders"); stats['total_orders'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='paid'"); stats['paid_orders'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE payment_method='stars'"); stats['stars_orders'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE payment_method='ton'"); stats['ton_orders'] = cur.fetchone()[0]
    cur.execute("""
        SELECT
            SUM(CASE WHEN o.payment_method='stars' AND o.status='paid' THEN p.price_stars ELSE 0 END) as total_stars,
            SUM(CASE WHEN o.payment_method='ton' AND o.status='paid' THEN p.price_ton ELSE 0 END) as total_ton
        FROM orders o
        JOIN products p ON o.product_id = p.id
    """)
    sums = cur.fetchone()
    stats['total_stars_earned'] = sums[0] or 0
    stats['total_ton_earned'] = sums[1] or 0
    conn.close()
    return stats