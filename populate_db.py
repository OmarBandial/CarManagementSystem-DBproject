import sqlite3
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()
conn = sqlite3.connect('dealership.db')
cur = conn.cursor()

# --- USERS ---
regions = ['Punjab', 'Balochistan', 'Sindh', 'KPK', 'North (Kashmir/Gilgit-Baltistan)']
user_ids = []
for _ in range(50):
    username = fake.unique.user_name()
    password = fake.password()
    age = random.randint(18, 70)
    region = random.choice(regions)
    is_admin = 0
    try:
        cur.execute("INSERT INTO users (username, password, age, region, is_admin) VALUES (?, ?, ?, ?, ?)",
                    (username, password, age, region, is_admin))
        user_ids.append(cur.lastrowid)
    except sqlite3.IntegrityError:
        continue
# Add one admin user
test_admin = ('admin', 'adminpass', 35, 'Punjab', 1)
try:
    cur.execute("INSERT INTO users (username, password, age, region, is_admin) VALUES (?, ?, ?, ?, ?)", test_admin)
    user_ids.append(cur.lastrowid)
except sqlite3.IntegrityError:
    pass

# --- CARS ---
brands = ['Toyota', 'Honda', 'Ford', 'BMW', 'Audi']
models = ['Sedan', 'SUV', 'Hatchback', 'Convertible', 'Truck']
car_ids = []
for _ in range(20):
    brand = random.choice(brands)
    model = random.choice(models)
    price = random.randint(10000, 50000)
    cost_price = price - random.randint(1000, 5000)
    stock = random.randint(1, 10)
    year = random.randint(2010, 2023)
    color = fake.color_name()
    mileage = random.randint(0, 150000)
    description = fake.text(max_nb_chars=100)
    cur.execute("""INSERT INTO cars (brand, model, price, cost_price, stock, year, color, mileage, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (brand, model, price, cost_price, stock, year, color, mileage, description))
    car_ids.append(cur.lastrowid)

# --- SALES ---
channels = ['website', 'showroom']
for _ in range(100):
    user_id = random.choice(user_ids)
    car_id = random.choice(car_ids)
    # Get car price and cost_price
    cur.execute("SELECT price, cost_price, stock FROM cars WHERE id = ?", (car_id,))
    car = cur.fetchone()
    if not car or car[2] <= 0:
        continue  # skip if out of stock
    sale_price = car[0] + random.randint(-2000, 2000)
    sale_date = fake.date_between(start_date='-2y', end_date='today')
    channel = random.choice(channels)
    discount_applied = random.choice([0, 500, 1000])
    # Insert sale
    cur.execute("""INSERT INTO sales (user_id, car_id, sale_price, sale_date, channel, discount_applied)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, car_id, sale_price, sale_date, channel, discount_applied))
    # Decrement stock
    cur.execute("UPDATE cars SET stock = stock - 1 WHERE id = ?", (car_id,))

conn.commit()
conn.close()
print("Database populated with random data!") 