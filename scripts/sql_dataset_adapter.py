import sqlite3
import pandas as pd
import numpy as np
import os
import argparse
import json
import sys

# Ensure generic_dataset_adapter can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from generic_dataset_adapter import adapt_dataset

def olist_preprocess(df):
    """Custom preprocessing hook for Olist dataset before the generic adapter mapping."""
    print("Applying Olist-specific preprocessing...")
    if 'review_comment_title' in df.columns and 'review_comment_message' in df.columns:
        df['review_comment_title'] = df['review_comment_title'].fillna('')
        df['review_comment_message'] = df['review_comment_message'].fillna('')
        df['review_text'] = (df['review_comment_title'] + " " + df['review_comment_message']).str.strip()
        df['review_text'] = df['review_text'].replace('', 'NO_REVIEW')
        df.drop(columns=['review_comment_title', 'review_comment_message'], inplace=True)
    
    if 'order_date' in df.columns:
        df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    if 'order_estimated_delivery_date' in df.columns:
        df['order_estimated_delivery_date'] = pd.to_datetime(df['order_estimated_delivery_date'], errors='coerce')
    if 'order_delivered_customer_date' in df.columns:
        df['order_delivered_customer_date'] = pd.to_datetime(df['order_delivered_customer_date'], errors='coerce')
    
    if 'order_estimated_delivery_date' in df.columns and 'order_date' in df.columns:
        df['expected_delivery_days'] = (df['order_estimated_delivery_date'] - df['order_date']).dt.days.fillna(0)
    if 'order_delivered_customer_date' in df.columns and 'order_date' in df.columns:
        df['actual_delivery_days'] = (df['order_delivered_customer_date'] - df['order_date']).dt.days.fillna(0)
    if 'actual_delivery_days' in df.columns and 'expected_delivery_days' in df.columns:
        df['delivery_delay'] = (df['actual_delivery_days'] - df['expected_delivery_days']).clip(lower=0)
    
    cols_to_drop = [c for c in ['order_estimated_delivery_date', 'order_delivered_customer_date'] if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    return df

def generate_olist_query(limit=None):
    limit_clause = f"LIMIT {limit}" if limit else ""
    return f"""
    WITH order_summary AS (
        SELECT oi.order_id, oi.product_id, oi.seller_id, COUNT(oi.order_item_id) as quantity, MAX(oi.price) as product_price, SUM(oi.price) as order_value, SUM(oi.freight_value) as freight_value
        FROM order_items oi GROUP BY oi.order_id, oi.product_id, oi.seller_id
    )
    SELECT o.order_id, o.order_purchase_timestamp as order_date, o.customer_id, os.product_id, pcnt.product_category_name_english as product_category, os.product_price, os.quantity, os.order_value, c.customer_city, s.seller_city as warehouse_city, o.order_estimated_delivery_date, o.order_delivered_customer_date, r.review_score as review_rating, r.review_comment_title, r.review_comment_message, r.review_creation_date as review_date
    FROM orders o
    JOIN order_summary os ON o.order_id = os.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN sellers s ON os.seller_id = s.seller_id
    JOIN products p ON os.product_id = p.product_id
    LEFT JOIN product_category_name_translation pcnt ON p.product_category_name = pcnt.product_category_name
    LEFT JOIN order_reviews r ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
    {limit_clause}
    """

def extract_and_map_database(db_path: str, output_csv: str, query: str = None, column_mapping: dict = None, dataset_name: str = "Database", limit: int = None, preprocess_hook = None):
    print(f"Connecting to database adapter: {dataset_name} at {db_path}")
    adapt_dataset(
        input_file=db_path, output_file=output_csv, column_mapping=column_mapping or {}, dataset_name=dataset_name, limit=limit, query=query, custom_preprocess_func=preprocess_hook
    )
    print(f"{dataset_name} data mapped successfully to: {output_csv}")
    return pd.read_csv(output_csv)

# Alias for backward compatibility if any old scripts still call it
extract_and_map_olist_data = extract_and_map_database

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal SQL Database Target Adapter")
    parser.add_argument('--limit', type=int, default=10000, help="Row limit for mapped output")
    parser.add_argument('--db_path', type=str, default=None, help="Path to the sqlite database")
    parser.add_argument('--output_csv', type=str, default=None, help="Output path for the mapped CSV")
    parser.add_argument('--query_file', type=str, default=None, help="Path to a .sql file containing the SELECT statement")
    parser.add_argument('--mapping_file', type=str, default=None, help="Path to a JSON file containing the dataset column mapping")
    parser.add_argument('--dataset_name', type=str, default="Database", help="Name of the Database/Dataset")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = args.db_path
    if not db_path:
        db_path = os.path.join(base_dir, 'data', 'olist.sqlite', 'olist.sqlite')
        if not os.path.exists(db_path): db_path = os.path.join(base_dir, 'data', 'olist.sqlite')

    out_path = args.output_csv
    if not out_path:
        out_path = os.path.join(base_dir, 'data', f'external_{args.dataset_name.lower().replace(" ","_")}_mapped.csv')

    if args.query_file and args.mapping_file:
        with open(args.query_file, 'r', encoding='utf-8') as f:
            query_str = f.read()
        with open(args.mapping_file, 'r', encoding='utf-8') as f:
             col_map = json.load(f)
        extract_and_map_database(db_path, out_path, query=query_str, column_mapping=col_map, dataset_name=args.dataset_name, limit=args.limit)
    else:
        print("No custom query/mapping provided. Defaulting to standard Olist pipeline mapping...")
        col_map = {
            "order_id": "order_id", "order_date": "order_date", "customer_id": "customer_id", "product_id": "product_id",
            "product_category": "product_category", "product_price": "product_price", "quantity": "quantity",
            "order_value": "order_value", "customer_city": "customer_city", "warehouse_city": "warehouse_city",
            "review_rating": "review_rating", "review_text": "review_text", "review_date": "review_date",
            "expected_delivery_days": "expected_delivery_days", "actual_delivery_days": "actual_delivery_days", "delivery_delay": "delivery_delay"
        }
        extract_and_map_database(db_path, out_path, query=generate_olist_query(args.limit), column_mapping=col_map, dataset_name="Olist", limit=args.limit, preprocess_hook=olist_preprocess)
