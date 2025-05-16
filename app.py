from flask import Flask, render_template, request, redirect, url_for, session, g, abort, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this in production
DATABASE = 'dealership.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    cars = []
    if 'user_id' in session:
        db = get_db()
        cars = db.execute('SELECT * FROM cars WHERE stock > 0 ORDER BY id DESC LIMIT 8').fetchall()
    return render_template('index.html', cars=cars[:4])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        age = request.form.get('age')
        region = request.form.get('region')
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password, age, region) VALUES (?, ?, ?, ?)',
                       (username, password, age, region))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/cars')
def cars():
    db = get_db()
    # Get filter parameters
    search = request.args.get('search', '').strip()
    brand = request.args.get('brand', '')
    car_type = request.args.get('type', '')
    year_min = request.args.get('year_min', type=int)
    year_max = request.args.get('year_max', type=int)
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)

    # Get available brands and types for filters
    brands = [row['brand'] for row in db.execute('SELECT DISTINCT brand FROM cars').fetchall()]
    types = [row['model'] for row in db.execute('SELECT DISTINCT model FROM cars').fetchall()]
    year_bounds = db.execute('SELECT MIN(year) as min_year, MAX(year) as max_year FROM cars').fetchone() or {'min_year': 2000, 'max_year': 2025}
    price_bounds = db.execute('SELECT MIN(price) as min_price, MAX(price) as max_price FROM cars').fetchone() or {'min_price': 0, 'max_price': 100000}
    # Fallbacks if DB returns None
    if year_bounds['min_year'] is None: year_bounds['min_year'] = 2000
    if year_bounds['max_year'] is None: year_bounds['max_year'] = 2025
    if price_bounds['min_price'] is None: price_bounds['min_price'] = 0
    if price_bounds['max_price'] is None: price_bounds['max_price'] = 100000

    # Build query
    query = 'SELECT * FROM cars WHERE stock > 0'
    params = []
    if search:
        query += ' AND (brand LIKE ? OR model LIKE ? OR description LIKE ? OR color LIKE ?)' 
        params += [f'%{search}%'] * 4
    if brand:
        query += ' AND brand = ?'
        params.append(brand)
    if car_type:
        query += ' AND model = ?'
        params.append(car_type)
    if year_min is not None:
        query += ' AND year >= ?'
        params.append(year_min)
    if year_max is not None:
        query += ' AND year <= ?'
        params.append(year_max)
    if price_min is not None:
        query += ' AND price >= ?'
        params.append(price_min)
    if price_max is not None:
        query += ' AND price <= ?'
        params.append(price_max)
    query += ' ORDER BY id DESC'
    cars = db.execute(query, params).fetchall()

    return render_template('cars.html', cars=cars, brands=brands, types=types,
        year_bounds=year_bounds, price_bounds=price_bounds,
        selected_brand=brand, selected_type=car_type, search=search,
        year_min=year_min, year_max=year_max, price_min=price_min, price_max=price_max)

@app.route('/car/<int:car_id>')
def car_details(car_id):
    db = get_db()
    car = db.execute('''
        SELECT id, brand, model, price, stock, year, color, mileage, description 
        FROM cars WHERE id = ?
    ''', (car_id,)).fetchone()
    if car is None:
        flash('Car not found', 'danger')
        return redirect(url_for('cars'))
    return render_template('car_details.html', car=car)

@app.route('/buy/<int:car_id>', methods=['POST'])
def buy_car(car_id):
    if 'user_id' not in session:
        flash('Please login to purchase a car', 'danger')
        return redirect(url_for('login'))
    
    db = get_db()
    car = db.execute('SELECT * FROM cars WHERE id = ? AND stock > 0', (car_id,)).fetchone()
    
    if not car:
        flash('Car not available', 'danger')
        return redirect(url_for('cars'))
    
    try:
        # Update stock
        db.execute('UPDATE cars SET stock = stock - 1 WHERE id = ?', (car_id,))
        # Record sale
        db.execute('''
            INSERT INTO sales (user_id, car_id, sale_price, sale_date, channel) 
            VALUES (?, ?, ?, datetime("now"), ?)
        ''', (session['user_id'], car_id, car['price'], 'website'))
        db.commit()
        flash(f'Successfully purchased {car["brand"]} {car["model"]}!', 'success')
    except sqlite3.Error as e:
        db.rollback()
        flash('An error occurred while processing your purchase', 'danger')
        return redirect(url_for('cars'))
    
    return redirect(url_for('purchase_history'))

@app.route('/admin/add_car', methods=['GET', 'POST'])
def add_car():
    if not session.get('is_admin'):
        abort(403)
    if request.method == 'POST':
        brand = request.form['brand']
        model = request.form['model']
        price = request.form['price']
        cost_price = request.form['cost_price']
        stock = request.form['stock']
        db = get_db()
        db.execute('INSERT INTO cars (brand, model, price, cost_price, stock) VALUES (?, ?, ?, ?, ?)',
                   (brand, model, price, cost_price, stock))
        db.commit()
        return redirect(url_for('cars'))
    return render_template('add_car.html')

@app.route('/history')
def purchase_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    purchases = db.execute('''
        SELECT sales.sale_date, cars.brand, cars.model, sales.sale_price
        FROM sales
        JOIN cars ON sales.car_id = cars.id
        WHERE sales.user_id = ?
        ORDER BY sales.sale_date DESC
    ''', (session['user_id'],)).fetchall()
    return render_template('purchase_history.html', purchases=purchases)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        abort(403)
    db = get_db()
    # Total sales count and revenue
    total_sales = db.execute('SELECT COUNT(*) as count, SUM(sale_price) as revenue FROM sales').fetchone()
    # Sales by brand/model
    sales_by_brand = db.execute('''
        SELECT cars.brand, cars.model, COUNT(sales.id) as num_sales, SUM(sales.sale_price) as total_revenue
        FROM sales
        JOIN cars ON sales.car_id = cars.id
        GROUP BY cars.brand, cars.model
        ORDER BY total_revenue DESC
    ''').fetchall()
    # Best selling cars (top 3)
    best_selling = db.execute('''
        SELECT cars.brand, cars.model, COUNT(sales.id) as num_sales
        FROM sales
        JOIN cars ON sales.car_id = cars.id
        GROUP BY cars.brand, cars.model
        ORDER BY num_sales DESC
        LIMIT 3
    ''').fetchall()
    page = request.args.get('page', 1, type=int)
    return render_template('admin_dashboard.html', total_sales=total_sales, sales_by_brand=sales_by_brand, best_selling=best_selling, page=page)

@app.route('/admin/analytics')
def admin_analytics():
    if not session.get('is_admin'):
        abort(403)
    db = get_db()
    # 1. Total Sales Overview (daily, monthly, yearly)
    sales_daily = db.execute("""
        SELECT strftime('%Y-%m-%d', sale_date) as period, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY period ORDER BY period DESC LIMIT 30
    """).fetchall()
    sales_monthly = db.execute("""
        SELECT strftime('%Y-%m', sale_date) as period, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY period ORDER BY period DESC LIMIT 12
    """).fetchall()
    sales_yearly = db.execute("""
        SELECT strftime('%Y', sale_date) as period, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY period ORDER BY period DESC
    """).fetchall()
    # 2. Sales by Brand/Model
    sales_by_brand = db.execute("""
        SELECT cars.brand, cars.model, COUNT(sales.id) as num_sales, SUM(sales.sale_price) as total_revenue
        FROM sales JOIN cars ON sales.car_id = cars.id
        GROUP BY cars.brand, cars.model ORDER BY total_revenue DESC
    """).fetchall()
    # 3. Best Selling Cars
    best_selling = db.execute("""
        SELECT cars.brand, cars.model, COUNT(sales.id) as num_sales
        FROM sales JOIN cars ON sales.car_id = cars.id
        GROUP BY cars.brand, cars.model ORDER BY num_sales DESC LIMIT 3
    """).fetchall()
    # 4. Customer Info
    customers = db.execute("""
        SELECT users.id, users.username, users.age, users.region, COUNT(sales.id) as purchases
        FROM users LEFT JOIN sales ON users.id = sales.user_id
        GROUP BY users.id ORDER BY purchases DESC
    """).fetchall()
    # 5. Sales by Region
    sales_by_region = db.execute("""
        SELECT users.region, COUNT(sales.id) as num_sales, SUM(sales.sale_price) as revenue
        FROM sales JOIN users ON sales.user_id = users.id
        GROUP BY users.region ORDER BY num_sales DESC
    """).fetchall()
    # 6. Monthly Sales Trend
    monthly_trend = db.execute("""
        SELECT strftime('%Y-%m', sale_date) as month, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY month ORDER BY month
    """).fetchall()
    # 7. Repeat vs New Customers
    repeat_vs_new = db.execute("""
        SELECT SUM(purchase_count = 1) as new_customers, SUM(purchase_count > 1) as repeat_customers
        FROM (SELECT user_id, COUNT(*) as purchase_count FROM sales GROUP BY user_id)
    """).fetchone()
    # 8. Low Stock Cars
    low_stock = db.execute("SELECT * FROM cars WHERE stock < 3").fetchall()
    # 9. Profit Analysis
    profit_analysis = db.execute("""
        SELECT sales.id, cars.brand, cars.model, sales.sale_price, cars.cost_price, (sales.sale_price - cars.cost_price) as profit
        FROM sales JOIN cars ON sales.car_id = cars.id
    """).fetchall()
    # 10. Sales Forecasting (simple avg of last 3 months)
    forecast = None
    if len(monthly_trend) >= 3:
        forecast = sum([row['count'] for row in monthly_trend[-3:]]) // 3
    # 11. Customer Categories
    customer_categories = db.execute("""
        SELECT users.id, users.username, SUM(sales.sale_price) as total_spent
        FROM users JOIN sales ON users.id = sales.user_id
        GROUP BY users.id ORDER BY total_spent DESC
    """).fetchall()
    # 12. Discount Impact
    discount_impact = db.execute("""
        SELECT SUM(CASE WHEN discount_applied > 0 THEN 1 ELSE 0 END) as discounted_sales,
               SUM(CASE WHEN discount_applied = 0 THEN 1 ELSE 0 END) as regular_sales
        FROM sales
    """).fetchone()
    # 13. Seasonal Sales Analysis
    seasonal_sales = db.execute("""
        SELECT strftime('%m', sale_date) as month, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY month ORDER BY month
    """).fetchall()
    # 14. Sales Channel Analysis
    channel_analysis = db.execute("""
        SELECT channel, COUNT(*) as count, SUM(sale_price) as revenue
        FROM sales GROUP BY channel
    """).fetchall()
    # 15. KPIs
    avg_price = db.execute("SELECT AVG(sale_price) as avg_price FROM sales").fetchone()
    top_region = db.execute("SELECT region, COUNT(*) as count FROM users GROUP BY region ORDER BY count DESC LIMIT 1").fetchone()
    total_sales = db.execute("SELECT COUNT(*) as total_sales FROM sales").fetchone()
    return render_template('admin_analytics.html',
        sales_daily=sales_daily, sales_monthly=sales_monthly, sales_yearly=sales_yearly,
        sales_by_brand=sales_by_brand, best_selling=best_selling, customers=customers,
        sales_by_region=sales_by_region, monthly_trend=monthly_trend, repeat_vs_new=repeat_vs_new,
        low_stock=low_stock, profit_analysis=profit_analysis, forecast=forecast,
        customer_categories=customer_categories, discount_impact=discount_impact,
        seasonal_sales=seasonal_sales, channel_analysis=channel_analysis,
        avg_price=avg_price, top_region=top_region, total_sales=total_sales
    )

if __name__ == '__main__':
    app.run(debug=True) 