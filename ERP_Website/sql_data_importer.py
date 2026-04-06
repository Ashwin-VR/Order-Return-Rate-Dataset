"""
ERP Return Prediction System
import_data.py — Run ONCE after db_setup.sql to load all CSVs into Oracle

Requirements:
    pip install oracledb pandas bcrypt

Place this file in the SAME folder as your 5 CSVs:
    customers.csv, orders.csv, products.csv, logistics.csv, returns.csv

Usage:
    python import_data.py
"""

import oracledb
import pandas as pd
import bcrypt
import os
import sys
from datetime import datetime

# ============================================================
# CONFIG — update password if different
# ============================================================
DB_CONFIG = {
    "user":     "SYSTEM",
    "password": "admin",
    "dsn":      "localhost:1521/FREEPDB1"
}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"   # login password for ERP portal

CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ============================================================
# CONNECT
# ============================================================
def get_connection():
    try:
        conn = oracledb.connect(**DB_CONFIG)
        print("✅ Connected to Oracle FREEPDB1 as erp_user")
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nMake sure you have run db_setup.sql first in SQL Developer.")
        sys.exit(1)

# ============================================================
# HELPER: batch insert with progress
# ============================================================
def batch_insert(cursor, sql, data, batch_size=500, label="rows"):
    total = len(data)
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        cursor.executemany(sql, batch)
        print(f"  Inserted {min(i+batch_size, total)}/{total} {label}")

# ============================================================
# 1. PRODUCTS
# ============================================================
def import_products(conn):
    print("\n📦 Importing products...")
    df = pd.read_csv(os.path.join(CSV_DIR, "products.csv"))

    # Ensure price_band is string
    df["price_band"] = df["price_band"].astype(str)

    sql = """
        INSERT INTO products (
            product_id, product_name, category, brand, price,
            price_band, product_return_rate, category_return_rate,
            avg_rating, rating_variance, size_variants_count, is_fragile
        ) VALUES (
            :1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12
        )
    """
    data = [
        (
            row["product_id"], row["product_name"], row["category"],
            row["brand"], float(row["price"]), str(row["price_band"]),
            float(row["product_return_rate"]), float(row["category_return_rate"]),
            float(row["avg_rating"]), float(row["rating_variance"]),
            int(row["size_variants_count"]), int(row["is_fragile"])
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        cur.executemany(sql, data)
    conn.commit()
    print(f"  ✅ {len(data)} products imported")

# ============================================================
# 2. CUSTOMERS
# ============================================================
def import_customers(conn):
    print("\n👤 Importing customers...")
    df = pd.read_csv(os.path.join(CSV_DIR, "customers.csv"))

    sql = """
        INSERT INTO customers (
            customer_id, city, state, pincode, customer_tenure_days,
            total_orders, total_returns, overall_return_rate,
            avg_order_value, avg_days_between_orders, last_order_days_ago,
            preferred_category, frequent_return_flag
        ) VALUES (
            :1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13
        )
    """
    data = [
        (
            row["customer_id"], row["city"], row["state"],
            int(row["pincode"]), int(row["customer_tenure_days"]),
            int(row["total_orders"]), int(row["total_returns"]),
            float(row["overall_return_rate"]), float(row["avg_order_value"]),
            float(row["avg_days_between_orders"]), int(row["last_order_days_ago"]),
            row["preferred_category"], int(row["frequent_return_flag"])
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        batch_insert(cur, sql, data, label="customers")
    conn.commit()
    print(f"  ✅ {len(data)} customers imported")

# ============================================================
# 3. ORDERS
# ============================================================
def import_orders(conn):
    print("\n🛒 Importing orders...")
    df = pd.read_csv(os.path.join(CSV_DIR, "orders.csv"))
    df["order_date"] = pd.to_datetime(df["order_date"])

    sql = """
        INSERT INTO orders (
            order_id, customer_id, product_id,
            order_date, order_day_of_week, order_hour,
            quantity, product_price, discount_amount,
            discount_percentage, final_price, payment_method, is_cod
        ) VALUES (
            :1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13
        )
    """
    data = [
        (
            row["order_id"], row["customer_id"], row["product_id"],
            row["order_date"].to_pydatetime(), row["order_day_of_week"],
            int(row["order_hour"]), int(row["quantity"]),
            float(row["product_price"]), float(row["discount_amount"]),
            int(row["discount_percentage"]), float(row["final_price"]),
            row["payment_method"], int(row["is_cod"])
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        batch_insert(cur, sql, data, label="orders")
    conn.commit()
    print(f"  ✅ {len(data)} orders imported")

# ============================================================
# 4. LOGISTICS
# ============================================================
def import_logistics(conn):
    print("\n🚚 Importing logistics...")
    df = pd.read_csv(os.path.join(CSV_DIR, "logistics.csv"))

    sql = """
        INSERT INTO logistics (
            order_id, shipping_mode, courier_partner,
            warehouse_city, delivery_city,
            expected_delivery_days, actual_delivery_days, delivery_delay,
            distance_km, is_remote_area, delivery_attempts,
            courier_delay_rate, warehouse_processing_time
        ) VALUES (
            :1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13
        )
    """
    data = [
        (
            row["order_id"], row["shipping_mode"], row["courier_partner"],
            row["warehouse_city"], row["delivery_city"],
            int(row["expected_delivery_days"]), int(row["actual_delivery_days"]),
            int(row["delivery_delay"]), int(row["distance_km"]),
            int(row["is_remote_area"]), int(row["delivery_attempts"]),
            float(row["courier_delay_rate"]), float(row["warehouse_processing_time"])
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        batch_insert(cur, sql, data, label="logistics rows")
    conn.commit()
    print(f"  ✅ {len(data)} logistics rows imported")

# ============================================================
# 5. RETURNS
# ============================================================
def import_returns(conn):
    print("\n↩️  Importing returns...")
    df = pd.read_csv(os.path.join(CSV_DIR, "returns.csv"))

    sql = """
        INSERT INTO returns (
            order_id, is_returned, return_reason, return_days_after_delivery
        ) VALUES (:1,:2,:3,:4)
    """
    data = [
        (
            row["order_id"], int(row["is_returned"]),
            row["return_reason"], int(row["return_days_after_delivery"])
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        batch_insert(cur, sql, data, label="return rows")
    conn.commit()
    print(f"  ✅ {len(data)} return rows imported")

# ============================================================
# 6. ADMIN USER (bcrypt hashed)
# ============================================================
def create_admin_user(conn):
    print("\n🔐 Creating admin user...")
    password_bytes = ADMIN_PASSWORD.encode("utf-8")
    hashed_pw = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    hash_pw_str = hashed_pw.decode("utf-8")

    username_bytes = ADMIN_USERNAME.encode("utf-8")
    hashed_un = bcrypt.hashpw(username_bytes, bcrypt.gensalt(rounds=12))
    hash_un_str = hashed_un.decode("utf-8")

    sql = """
        INSERT INTO erp_users (username, password_hash, full_name, role)
        VALUES (:1, :2, :3, :4)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (hash_un_str, hash_pw_str, "ERP Administrator", "admin"))
    conn.commit()
    print(f"  ✅ Admin user created — login: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")

# ============================================================
# 7. VERIFY COUNTS
# ============================================================
def verify_counts(conn):
    print("\n📊 Verification:")
    tables = {
        "products":  6,
        "customers": 100,
        "orders":    3000,
        "logistics": 3000,
        "returns":   3000,
        "erp_users": 1
    }
    all_ok = True
    with conn.cursor() as cur:
        for table, expected in tables.items():
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            status = "✅" if count == expected else "⚠️ "
            if count != expected:
                all_ok = False
            print(f"  {status} {table:<12} {count:>5} rows  (expected {expected})")

    if all_ok:
        print("\n🎉 All tables loaded correctly. Ready to train model.")
    else:
        print("\n⚠️  Some counts don't match. Check CSV files and re-run.")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  ERP Return Prediction — Oracle DB Import")
    print("=" * 55)

    conn = get_connection()

    try:
        import_products(conn)
        import_customers(conn)
        import_orders(conn)
        import_logistics(conn)
        import_returns(conn)
        create_admin_user(conn)
        verify_counts(conn)
    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        print("\n🔌 Connection closed.")
