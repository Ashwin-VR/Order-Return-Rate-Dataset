import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Fix seeds strictly for deterministic, consistent ML training sets
np.random.seed(42)
random.seed(42)

NUM_CUSTOMERS = 500
NUM_ORDERS = 10000

# -----------------------------
# CUSTOMERS
# -----------------------------
customers = []

for i in range(NUM_CUSTOMERS):
    # Customer persona dictates behavior
    persona = np.random.choice(['Bargain Hunter', 'Loyal', 'Impulse Buyer'])
    
    if persona == 'Bargain Hunter':
        base_return = np.random.uniform(0.15, 0.35)
        avg_value = np.random.randint(50, 500)
        tenure = np.random.randint(10, 365)
    elif persona == 'Loyal':
        base_return = np.random.uniform(0.01, 0.10)
        avg_value = np.random.randint(200, 2000)
        tenure = np.random.randint(365, 1500)
    else:
        base_return = np.random.uniform(0.20, 0.40)
        avg_value = np.random.randint(100, 3000)
        tenure = np.random.randint(1, 100)

    customers.append([
        f"C{i+1}", persona, base_return, tenure, avg_value
    ])

customer_df = pd.DataFrame(customers, columns=[
    "customer_id", "persona", "base_return_rate",
    "customer_tenure_days", "avg_order_value"
])

# -----------------------------
# PRODUCTS
# -----------------------------
products = []
CATEGORIES = ["Apparel", "Electronics", "Footwear", "Home", "Beauty"]

for i in range(50):
    category = np.random.choice(CATEGORIES)
    
    # Feature Correlation: Electronics = higher price, higher rating strictness
    if category == "Electronics":
        price = np.random.randint(100, 3000)
        rating = np.random.uniform(3.0, 5.0)
    elif category in ["Apparel", "Footwear"]:
        price = np.random.randint(20, 300)
        rating = np.random.uniform(2.0, 4.5)
    else:
        price = np.random.randint(10, 500)
        rating = np.random.uniform(3.5, 4.9)

    products.append([f"P{i+1}", price, rating, category])

product_df = pd.DataFrame(products, columns=[
    "product_id", "price", "rating", "category"
])

# -----------------------------
# ORDERS (WITH DETERMINISTIC RULE-BASED ML PATTERNS)
# -----------------------------
orders = []
start_date = datetime(2023, 1, 1)

# Vectorizing the generation or using loop for complex conditional logic
for i in range(NUM_ORDERS):
    cust = customer_df.sample(1).iloc[0]
    prod = product_df.sample(1).iloc[0]

    # Time feature
    order_date = start_date + timedelta(days=np.random.randint(0, 365))
    is_holiday_season = 1 if order_date.month in [11, 12] else 0

    # Interaction dynamics
    delay = np.random.choice([0,1,2,3,5,10], p=[0.4, 0.2, 0.15, 0.1, 0.05, 0.1])
    
    if cust["persona"] == "Bargain Hunter":
        discount = np.random.choice([20, 30, 50, 70])
    else:
        discount = np.random.choice([0, 5, 10, 20], p=[0.6, 0.2, 0.1, 0.1])
        
    # --- NONLINEAR & INTERACTION DETERMINISTIC MODEL ---
    # Start with customer base
    prob = cust["base_return_rate"]
    
    # Rule 1: Apparel/Footwear + High Delay = Huge surge in return
    if prod["category"] in ["Apparel", "Footwear"] and delay > 3:
        prob += 0.35
    elif prod["category"] == "Electronics" and delay > 2:
        prob += 0.10 # Electronics buyers care less about delay

    # Rule 2: Low rating sharply increases return probabilty (exponentially)
    if prod["rating"] < 3.0:
        prob += (3.0 - prod["rating"]) * 0.25
        
    # Rule 3: High discount on Apparel usually means final sale / impulsive, highly returned
    if count := (discount >= 50 and prod["category"] == "Apparel"):
        prob += 0.20
        
    # Rule 4: Holiday impulse buying
    if is_holiday_season and cust["persona"] == "Impulse Buyer":
        prob += 0.15
        
    # Rule 5: Nonlinear tenure effect (Longer tenure drops return chance, but levels off)
    prob -= np.log1p(cust["customer_tenure_days"]) * 0.02
    
    # Very small noise (SNR is high, model *will* find these rules)
    noise = np.random.normal(0, 0.02)
    prob = np.clip(prob + noise, 0, 1)

    # Hard threshold classification
    is_returned = int(prob > 0.5)

    orders.append([
        f"ORD{i+1}",
        cust["customer_id"],
        prod["product_id"],
        order_date.strftime("%Y-%m-%d"),
        delay,
        discount,
        is_holiday_season,
        prob,
        is_returned
    ])

orders_df = pd.DataFrame(orders, columns=[
    "order_id", "customer_id", "product_id", "order_date",
    "delivery_delay", "discount_pct", "is_holiday_season",
    "return_probability", "is_returned"
])

# Merge everything for a completely enriched dataset ready for ML models
final_merged_df = orders_df.merge(customer_df, on="customer_id").merge(product_df, on="product_id")

# -----------------------------
# SAVE
# -----------------------------
customer_df.to_csv("customers.csv", index=False)
product_df.to_csv("products.csv", index=False)
final_merged_df.to_csv("orders.csv", index=False)

print("✅ Complex, ML-friendly deterministic synthetic data generated!")
