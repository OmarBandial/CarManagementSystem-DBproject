-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL, -- Plain text for demo only
    is_admin INTEGER DEFAULT 0, -- 0 = customer, 1 = admin
    age INTEGER,
    region TEXT CHECK(region IN ('Punjab', 'Balochistan', 'Sindh', 'KPK', 'North (Kashmir/Gilgit-Baltistan)'))
);

-- Cars table
CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    price REAL NOT NULL,
    cost_price REAL NOT NULL,
    stock INTEGER NOT NULL,
    year INTEGER,
    color TEXT,
    mileage INTEGER,
    description TEXT
);

-- Sales table
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    car_id INTEGER NOT NULL,
    sale_price REAL NOT NULL,
    sale_date TEXT NOT NULL,
    channel TEXT, -- e.g., 'website', 'showroom'
    discount_applied REAL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(car_id) REFERENCES cars(id)
);

-- Offers table
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    car_id INTEGER,
    discount REAL NOT NULL,
    valid_until TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(car_id) REFERENCES cars(id)
); 