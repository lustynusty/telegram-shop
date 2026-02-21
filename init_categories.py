# init_categories.py
import sqlite3
from database import add_category

names = [
    {"name": "Лера", "icon": "👩", "desc": "Товары Леры"},
    {"name": "Катя", "icon": "👩", "desc": "Товары Кати"},
    {"name": "Настя", "icon": "👩", "desc": "Товары Насти"},
    {"name": "Лена", "icon": "👩", "desc": "Товары Лены"},
    {"name": "Оля", "icon": "👩", "desc": "Товары Оли"},
]

for p in names:
    add_category(p["name"], p["desc"], p["icon"])
print("Категории созданы.")