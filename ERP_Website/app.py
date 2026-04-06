import os
import json
import csv
import io
import joblib
import pgeocode
import math
from datetime import datetime
from functools import wraps

import bcrypt
import oracledb
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify, make_response)
from sqlalchemy import create_engine, text

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'erp_return_predictor_2026'

DB_URL = "oracle+oracledb://SYSTEM:admin@localhost:1521/?service_name=FREEPDB1"
engine = create_engine(DB_URL, pool_pre_ping=True)

# ─── Model Loading ─────────────────────────────────────────────────────────────
from model_trainer import predict_single

model = joblib.load('model.pkl')
feature_cols = joblib.load('feature_columns.pkl')
with open('feature_importance.json', 'r') as f:
    feature_importance = json.load(f)

model_report = {}
try:
    with open('model_report.txt', 'r') as f:
        for line in f:
            if ':' in line:
                k, v = line.strip().split(':', 1)
                model_report[k.strip()] = v.strip()
except Exception:
    model_report = {'ROC-AUC': 'N/A', 'Recall': 'N/A', 'Precision': 'N/A'}

import decimal

# ─── DB Helper ─────────────────────────────────────────────────────────────────
def get_db():
    return engine.connect()

def rows_to_dicts(result):
    keys = [k.lower() for k in result.keys()]
    dicts = []
    for row in result.fetchall():
        d = {}
        for k, v in zip(keys, row):
            if isinstance(v, decimal.Decimal):
                d[k] = float(v)
            else:
                d[k] = v
        dicts.append(d)
    return dicts

# ─── Auth ──────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─── Page Routes ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['user'])

@app.route('/simulate')
@login_required
def simulate():
    return render_template('simulate.html', username=session['user'])

@app.route('/orders')
@login_required
def orders():
    return render_template('orders.html', username=session['user'])

@app.route('/customers')
@login_required
def customers():
    return render_template('customers.html', username=session['user'])

# ─── Auth API ──────────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    try:
        with get_db() as conn:
            result = conn.execute(text("SELECT username, password_hash FROM erp_users"))
            rows = result.fetchall()
            
        for row in rows:
            db_user_hash = row[0]
            db_pass_hash = row[1]
            if bcrypt.checkpw(username.encode(), db_user_hash.encode()):
                if bcrypt.checkpw(password.encode(), db_pass_hash.encode()):
                    session['user'] = username
                    return jsonify({'success': True})
                break # Matched username but wrong password
                
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

# ─── Dashboard KPIs ────────────────────────────────────────────────────────────
@app.route('/api/dashboard/kpis')
@login_required
def api_dashboard_kpis():
    try:
        with get_db() as conn:
            total_orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            ret = conn.execute(text(
                "SELECT COUNT(*) FROM returns WHERE is_returned = 1"
            )).scalar()
            overall_return_rate = round((ret / total_orders * 100), 1) if total_orders else 0

            avg_delay = conn.execute(text(
                "SELECT ROUND(AVG(delivery_delay), 1) FROM logistics"
            )).scalar() or 0

            cod_count = conn.execute(text(
                "SELECT COUNT(*) FROM orders WHERE is_cod = 1"
            )).scalar()
            cod_pct = round((cod_count / total_orders * 100), 1) if total_orders else 0

            high_risk = conn.execute(text(
                "SELECT COUNT(*) FROM order_predictions WHERE risk_tier = 'HIGH'"
            )).scalar() or 0

            projected_savings = int(high_risk * 0.65 * 0.30 * 300)

        return jsonify({
            'total_orders': total_orders,
            'overall_return_rate': overall_return_rate,
            'avg_delivery_delay': float(avg_delay),
            'cod_pct': cod_pct,
            'high_risk_orders': high_risk,
            'projected_savings': projected_savings,
            'returned_count': ret
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

# ─── Chart APIs ────────────────────────────────────────────────────────────────
@app.route('/api/charts/return-overview')
@login_required
def chart_return_overview():
    try:
        with get_db() as conn:
            r = conn.execute(text("SELECT COUNT(*) FROM returns WHERE is_returned = 1")).scalar()
            nr = conn.execute(text("SELECT COUNT(*) FROM returns WHERE is_returned = 0")).scalar()
        return jsonify({'returned': r, 'not_returned': nr})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/return-by-payment')
@login_required
def chart_return_by_payment():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT o.payment_method,
                       COUNT(*) AS total,
                       SUM(r.is_returned) AS returned
                FROM orders o
                JOIN returns r ON o.order_id = r.order_id
                GROUP BY o.payment_method
            """))
            rows = rows_to_dicts(result)
        data = []
        for row in rows:
            total = row['total'] or 1
            data.append({
                'method': row['payment_method'],
                'rate': round(row['returned'] / total * 100, 1)
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/return-by-delay')
@login_required
def chart_return_by_delay():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT l.delivery_delay,
                       SUM(r.is_returned) AS returned,
                       COUNT(*) - SUM(r.is_returned) AS not_returned
                FROM logistics l
                JOIN returns r ON l.order_id = r.order_id
                WHERE l.delivery_delay BETWEEN 0 AND 3
                GROUP BY l.delivery_delay
                ORDER BY l.delivery_delay
            """))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/return-by-category')
@login_required
def chart_return_by_category():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT p.category,
                       COUNT(*) AS total,
                       SUM(r.is_returned) AS returned
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
                JOIN returns r ON o.order_id = r.order_id
                GROUP BY p.category
            """))
            rows = rows_to_dicts(result)
        data = []
        for row in rows:
            total = row['total'] or 1
            rate = round(row['returned'] / total * 100, 1)
            data.append({'category': row['category'], 'rate': rate})
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/orders-by-city')
@login_required
def chart_orders_by_city():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT delivery_city, COUNT(*) AS total
                FROM logistics
                GROUP BY delivery_city
                ORDER BY total DESC
                FETCH FIRST 8 ROWS ONLY
            """))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/city-stacked')
@login_required
def chart_city_stacked():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT l.delivery_city,
                       SUM(r.is_returned) AS returned,
                       COUNT(*) - SUM(r.is_returned) AS not_returned
                FROM logistics l
                JOIN returns r ON l.order_id = r.order_id
                GROUP BY l.delivery_city
                ORDER BY (SUM(r.is_returned) + COUNT(*)) DESC
                FETCH FIRST 8 ROWS ONLY
            """))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/product-return-rate')
@login_required
def chart_product_return_rate():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT p.product_id, p.product_name,
                       COUNT(*) AS total,
                       SUM(r.is_returned) AS returned
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
                JOIN returns r ON o.order_id = r.order_id
                GROUP BY p.product_id, p.product_name
                ORDER BY p.product_id
            """))
            rows = rows_to_dicts(result)
        data = []
        for row in rows:
            total = row['total'] or 1
            rate = round(row['returned'] / total * 100, 1)
            data.append({
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'rate': rate
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/return-reasons')
@login_required
def chart_return_reasons():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT return_reason, COUNT(*) AS cnt
                FROM returns
                WHERE is_returned = 1 AND return_reason IS NOT NULL
                GROUP BY return_reason
                ORDER BY cnt DESC
            """))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/courier-performance')
@login_required
def chart_courier_performance():
    try:
        with get_db() as conn:
            result = conn.execute(text("""
                SELECT courier_partner,
                       COUNT(*) AS total_shipments,
                       ROUND(AVG(courier_delay_rate), 3) AS avg_delay_rate,
                       ROUND(AVG(actual_delivery_days), 1) AS avg_delivery_days,
                       ROUND(SUM(CASE WHEN delivery_delay <= 0 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS on_time_pct
                FROM logistics
                GROUP BY courier_partner
                ORDER BY courier_partner
            """))
            rows = rows_to_dicts(result)
        for row in rows:
            rate = row['avg_delay_rate'] or 0
            if rate > 0.20:
                row['risk_level'] = 'HIGH'
            elif rate > 0.10:
                row['risk_level'] = 'MEDIUM'
            else:
                row['risk_level'] = 'LOW'
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Dropdowns ─────────────────────────────────────────────────────────────────
@app.route('/api/customers/dropdown')
@login_required
def customers_dropdown():
    try:
        with get_db() as conn:
            result = conn.execute(text(
                "SELECT customer_id, city, overall_return_rate FROM customers ORDER BY customer_id"
            ))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/dropdown')
@login_required
def products_dropdown():
    try:
        with get_db() as conn:
            result = conn.execute(text(
                "SELECT product_id, product_name, category, price FROM products ORDER BY product_id"
            ))
            rows = rows_to_dicts(result)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Prediction Helpers ────────────────────────────────────────────────────────
def build_order_dict(form, customer_row, product_row):
    """Construct order dict for predict_single. Never include post-delivery fields."""
    payment = form.get('payment_method', 'COD')
    is_cod = 1 if payment == 'COD' else 0
    discount_pct = float(form.get('discount_percentage', 0))
    final_price = float(product_row['price']) * (1 - discount_pct / 100)

    dist_calc = pgeocode.GeoDistance('IN')
    val = dist_calc.query_postal_code(str(form.get('source_pincode', '400001')), str(form.get('dest_pincode', '110001')))
    distance_km = 500.0 if math.isnan(val) else float(val)

    return {
        # Customer
        'customer_id': customer_row['customer_id'],
        'city': customer_row['city'],
        'state': customer_row.get('state', ''),
        'pincode': customer_row.get('pincode', ''),
        'customer_tenure_days': customer_row['customer_tenure_days'],
        'total_orders': customer_row['total_orders'],
        'total_returns': customer_row['total_returns'],
        'overall_return_rate': customer_row['overall_return_rate'],
        'avg_order_value': customer_row['avg_order_value'],
        'avg_days_between_orders': customer_row['avg_days_between_orders'],
        'last_order_days_ago': customer_row['last_order_days_ago'],
        'preferred_category': customer_row['preferred_category'],
        'frequent_return_flag': customer_row['frequent_return_flag'],

        # Product
        'product_id': product_row['product_id'],
        'product_name': product_row['product_name'],
        'category': product_row['category'],
        'brand': product_row.get('brand', ''),
        'price': float(product_row['price']),
        'price_band': product_row.get('price_band', ''),
        'product_return_rate': product_row.get('product_return_rate', 0),
        'category_return_rate': product_row.get('category_return_rate', 0),
        'avg_rating': product_row.get('avg_rating', 4.0),
        'rating_variance': product_row.get('rating_variance', 0),
        'size_variants_count': product_row.get('size_variants_count', 1),
        'is_fragile': product_row.get('is_fragile', 0),

        # Order
        'quantity': int(form.get('quantity', 1)),
        'product_price': float(product_row['price']),
        'discount_amount': float(product_row['price']) * discount_pct / 100,
        'discount_percentage': discount_pct,
        'final_price': final_price,
        'payment_method': payment,
        'is_cod': is_cod,
        'order_day_of_week': datetime.now().weekday(),
        'order_hour': int(form.get('order_hour', 12)),

        # Logistics (pre-delivery only)
        'shipping_mode': form.get('shipping_mode', 'Standard'),
        'courier_partner': form.get('courier_partner', 'Delhivery'),
        'warehouse_city': form.get('warehouse_city', 'Mumbai'),
        'delivery_city': form.get('delivery_city', ''),
        'expected_delivery_days': 5,
        'distance_km': distance_km,
        'is_remote_area': 0,
        'delivery_attempts': 1,
        'courier_delay_rate': 0.10,
        'warehouse_processing_time': 1,
    }

def get_erp_actions(dominant_reason, form, prediction, customer_row, product_row, history=[]):
    actions = []
    category = product_row.get('category', '')
    payment = form.get('payment_method', 'COD')
    discount_pct = float(form.get('discount_percentage', 0))
    predicted_prob = prediction.get('predicted_prob', 0)
    risk_tier = prediction.get('risk_tier', 'LOW')
    courier_delay_rate = 0.10  # default; in production pull from logistics

    # Reason-based actions
    if dominant_reason == 'SIZE_FIT_ISSUE':
        actions.append({'icon': '', 'title': 'Include printed size guide insert',
                        'rationale': 'This customer most frequently returns due to size/fit issues.',
                        'trigger': 'Triggered by: historical return reason = SIZE_FIT_ISSUE'})
        actions.append({'icon': '', 'title': 'Schedule proactive sizing call before dispatch',
                        'rationale': 'A pre-dispatch sizing confirmation reduces size-related returns.',
                        'trigger': 'Triggered by: SIZE_FIT_ISSUE pattern in customer history'})
    elif dominant_reason == 'DELIVERY_DELAY':
        actions.append({'icon': '', 'title': 'Switch courier to BlueDart Express',
                        'rationale': 'Customer is delay-sensitive based on past returns.',
                        'trigger': 'Triggered by: DELIVERY_DELAY as top return reason'})
        actions.append({'icon': '', 'title': 'Add 1-day buffer to delivery promise',
                        'rationale': 'Setting accurate expectations reduces frustration-driven returns.',
                        'trigger': 'Triggered by: DELIVERY_DELAY history'})
    elif dominant_reason == 'QUALITY_DEFECT':
        actions.append({'icon': '', 'title': 'Flag for QC inspection before dispatch',
                        'rationale': 'Customer has returned items citing quality defects.',
                        'trigger': 'Triggered by: QUALITY_DEFECT return reason'})
        actions.append({'icon': '', 'title': 'Photograph item before sealing package',
                        'rationale': 'Visual record protects against disputed quality claims.',
                        'trigger': 'Triggered by: QUALITY_DEFECT history'})
    elif dominant_reason == 'NO_LONGER_NEEDED':
        actions.append({'icon': '', 'title': 'Add 2-hour SMS order confirmation window',
                        'rationale': 'Gives buyer a chance to cancel impulsive orders.',
                        'trigger': 'Triggered by: NO_LONGER_NEEDED return pattern'})
    elif dominant_reason == 'NOT_AS_DESCRIBED':
        actions.append({'icon': '', 'title': 'Attach printed product spec sheet',
                        'rationale': 'Reduces expectation mismatch.',
                        'trigger': 'Triggered by: NOT_AS_DESCRIBED return history'})
        actions.append({'icon': '', 'title': 'Send product photo to customer before dispatch',
                        'rationale': 'Allows customer to confirm item matches expectation.',
                        'trigger': 'Triggered by: NOT_AS_DESCRIBED reason'})
    elif dominant_reason == 'WRONG_ITEM':
        actions.append({'icon': '', 'title': 'Double-check SKU at packing station',
                        'rationale': 'Prevents wrong item dispatch errors.',
                        'trigger': 'Triggered by: WRONG_ITEM return reason'})
        actions.append({'icon': '', 'title': 'Require packer signature on this order',
                        'rationale': 'Adds accountability at packing stage.',
                        'trigger': 'Triggered by: WRONG_ITEM history'})
    else:
        # Category-level fallback
        if category in ['Apparel', 'Footwear']:
            actions.append({'icon': '', 'title': 'Include size guide (category default)',
                            'rationale': 'Size-sensitive category with no specific return history from this customer.',
                            'trigger': f'Triggered by: category = {category}'})
        elif category == 'Electronics':
            actions.append({'icon': '', 'title': 'QC check before dispatch (Electronics default)',
                            'rationale': 'Electronics have higher general defect rates.',
                            'trigger': 'Triggered by: category = Electronics'})
                            
        # History contextualizer fallback
        if len(history) > 0:
            actions.append({'icon': '', 'title': 'Dispatch normally',
                            'rationale': 'Customer has ordered this item before successfully without returning it.',
                            'trigger': f'{len(history)} prior successful orders found'})
        else:
            actions.append({'icon': '', 'title': 'Dispatch normally',
                            'rationale': 'No specific return history to act on for this new product.',
                            'trigger': 'No prior customer-product history found'})

    # Always-on rules
    if payment == 'COD' and risk_tier == 'HIGH':
        actions.append({'icon': '', 'title': 'Call customer to confirm order intent before shipping',
                        'rationale': 'COD orders with high return risk have higher non-acceptance rates.',
                        'trigger': f'Triggered by: COD payment + {round(predicted_prob*100,1)}% predicted return risk'})

    if courier_delay_rate > 0.20:
        actions.append({'icon': '', 'title': 'High courier delay rate — consider switching to BlueDart',
                        'rationale': 'Selected courier has elevated delay rates.',
                        'trigger': f'Triggered by: courier_delay_rate = {courier_delay_rate}'})

    if predicted_prob > 0.80:
        actions.append({'icon': '', 'title': 'Risk exceeds 80% — hold for manual manager review',
                        'rationale': 'Extreme return probability warrants human review before dispatch.',
                        'trigger': f'Triggered by: predicted_prob = {round(predicted_prob*100,1)}%'})

    if discount_pct >= 30 and category in ['Apparel', 'Footwear']:
        actions.append({'icon': '', 'title': 'High discount on size-sensitive product — add size confirmation',
                        'rationale': 'Discounted size-sensitive items have elevated return rates.',
                        'trigger': f'Triggered by: {discount_pct}% discount on {category}'})

    return actions

@app.route('/api/predict-live', methods=['POST'])
@login_required
def api_predict_live():
    try:
        form = request.get_json()
        customer_id = form.get('customer_id')
        product_id = form.get('product_id')
        if not customer_id or not product_id:
            return jsonify({'predicted_prob': 0, 'predicted_pct': 0, 'risk_tier': 'LOW'})

        with get_db() as conn:
            cr = conn.execute(text("SELECT * FROM customers WHERE customer_id = :id"), {'id': customer_id})
            customer_row = rows_to_dicts(cr)
            pr = conn.execute(text("SELECT * FROM products WHERE product_id = :id"), {'id': product_id})
            product_row = rows_to_dicts(pr)

        if not customer_row or not product_row:
            return jsonify({'predicted_prob': 0, 'predicted_pct': 0, 'risk_tier': 'LOW'})

        order_dict = build_order_dict(form, customer_row[0], product_row[0])
        result = predict_single(order_dict)
        return jsonify({
            'predicted_prob': result['predicted_prob'],
            'predicted_pct': round(result['predicted_prob'] * 100, 1),
            'risk_tier': result['risk_tier']
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/simulate', methods=['POST'])
@login_required
def api_simulate():
    try:
        form = request.get_json()
        customer_id = form.get('customer_id')
        product_id = form.get('product_id')

        with get_db() as conn:
            cr = conn.execute(text("SELECT * FROM customers WHERE customer_id = :id"), {'id': customer_id})
            customer_row = rows_to_dicts(cr)[0]
            pr = conn.execute(text("SELECT * FROM products WHERE product_id = :id"), {'id': product_id})
            product_row = rows_to_dicts(pr)[0]

            # History
            hist_r = conn.execute(text("""
                SELECT o.order_id, o.order_date, o.quantity, o.discount_percentage,
                       o.payment_method, r.is_returned, r.return_reason
                FROM orders o
                JOIN returns r ON o.order_id = r.order_id
                WHERE o.customer_id = :cid AND o.product_id = :pid
                ORDER BY o.order_date DESC
            """), {'cid': customer_id, 'pid': product_id})
            history = rows_to_dicts(hist_r)

        order_dict = build_order_dict(form, customer_row, product_row)
        result = predict_single(order_dict)

        # Top drivers
        top_drivers = []
        for item in sorted(feature_importance, key=lambda x: -x['importance'])[:3]:
            feat = item['feature']
            clean_feat = feat.replace('category_', 'Category: ').replace('payment_method_', 'Payment: ').replace('_', ' ').title()
            imp = item['importance']
            
            explanations = {
                'overall_return_rate': f"This customer returned {round(float(customer_row.get('overall_return_rate', 0))*100, 1)}% of past orders",
                'frequent_return_flag': "Customer is flagged as a frequent returner",
                'is_cod': "Cash on delivery orders carry higher risk",
                'discount_percentage': f"Order has a {form.get('discount_percentage', 0)}% discount",
                'product_return_rate': f"Product historic return rate is {round(float(product_row.get('product_return_rate', 0))*100, 1)}%",
                'courier_delay_rate': f"Courier has a mathematically significant delay risk",
                'distance_km': f"Delivery distance of {form.get('distance_km', 'N/A')} km heavily impacts timeline",
                'high_value_delayed': "High value orders combined with shipping delays trigger severe risk escalations"
            }
            
            expl = explanations.get(feat, f"The Decision Engine identified {clean_feat} as a historically proven return driver.")
            
            top_drivers.append({
                'feature': clean_feat,
                # Multiply importance purely strictly for a visual frontend boost on the bar as per user request
                'importance': float(imp) * 1.5, 
                'explanation': expl
            })

        # Dominant reason
        reasons = [h['return_reason'] for h in history if h.get('is_returned') and h.get('return_reason')]
        dominant_reason = max(set(reasons), key=reasons.count) if reasons else None

        # Generate Actions
        erp_actions = get_erp_actions(dominant_reason, form, result, customer_row, product_row, history)
        
        # Action Agent: Long distances buffer
        dist = form.get('distance_km', 0)
        try:
            dist_f = float(dist)
        except:
            dist_f = 0
            
        if dist_f > 1000:
            erp_actions.append({
                'icon': '', 'title': 'Add 2-day delivery buffer to ETA',
                'rationale': 'Very large distances between the warehouse and customer location strictly require extra buffering to prevent delay-related return risk.',
                'trigger': f'Distance naturally exceeds 1000km range ({int(dist_f)}km)'
            })

        return jsonify({
            'prediction': {
                'predicted_prob': result['predicted_prob'],
                'predicted_pct': round(result['predicted_prob'] * 100, 1),
                'risk_tier': result['risk_tier'],
                'top_drivers': top_drivers
            },
            'customer_history': history,
            'erp_actions': erp_actions,
            'customer_data': customer_row,
            'product_data': product_row
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

# ─── Orders Table ──────────────────────────────────────────────────────────────
@app.route('/api/orders')
@login_required
def api_orders():
    try:
        page = int(request.args.get('page', 1))
        per_page = 50
        offset = (page - 1) * per_page

        risk_tier = request.args.get('risk_tier', '')
        payment = request.args.get('payment_method', '')
        category = request.args.get('category', '')
        city = request.args.get('city', '')
        returned = request.args.get('returned', '')
        search = request.args.get('search', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        where_clauses = []
        params = {}

        if search:
            where_clauses.append("o.order_id LIKE :search")
            params['search'] = f'%{search}%'
        if payment:
            where_clauses.append("o.payment_method = :payment")
            params['payment'] = payment
        if category:
            where_clauses.append("p.category = :category")
            params['category'] = category
        if city:
            where_clauses.append("l.delivery_city = :city")
            params['city'] = city
        if returned == '1':
            where_clauses.append("r.is_returned = 1")
        elif returned == '0':
            where_clauses.append("r.is_returned = 0")
        if risk_tier:
            where_clauses.append("op.risk_tier = :risk_tier")
            params['risk_tier'] = risk_tier
        if date_from:
            where_clauses.append("o.order_date >= TO_DATE(:date_from, 'YYYY-MM-DD')")
            params['date_from'] = date_from
        if date_to:
            where_clauses.append("o.order_date <= TO_DATE(:date_to, 'YYYY-MM-DD')")
            params['date_to'] = date_to

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        base_query = f"""
            SELECT o.order_id, o.order_date, o.customer_id, o.product_id,
                   p.product_name, p.category,
                   o.quantity, o.discount_percentage, o.payment_method,
                   l.courier_partner, l.delivery_city,
                   op.predicted_return_prob AS predicted_prob,
                   r.is_returned, r.return_reason
            FROM orders o
            JOIN products p ON o.product_id = p.product_id
            JOIN logistics l ON o.order_id = l.order_id
            JOIN returns r ON o.order_id = r.order_id
            LEFT JOIN order_predictions op ON o.order_id = op.order_id
            {where_sql}
        """

        with get_db() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM ({base_query})"), params)
            total = count_result.scalar()

            paginated = conn.execute(text(f"""
                SELECT * FROM (
                    SELECT q.*, ROWNUM rn FROM ({base_query} ORDER BY TO_NUMBER(SUBSTR(o.order_id, 2)) ASC) q
                    WHERE ROWNUM <= :end_row
                )
                WHERE rn > :start_row
            """), {**params, 'end_row': page * per_page, 'start_row': offset})
            rows = rows_to_dicts(paginated)

        # Format dates
        for row in rows:
            if row.get('order_date'):
                d = str(row['order_date'])[:10]
                row['order_date'] = f"{d[8:10]}-{d[5:7]}-{d[0:4]}" if len(d) == 10 else d
            row['predicted_pct'] = round(float(row['predicted_prob']) * 100, 1) if row.get('predicted_prob') is not None else None

        return jsonify({'rows': rows, 'total': total, 'page': page, 'per_page': per_page})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/orders/export')
@login_required
def api_orders_export():
    try:
        risk_tier = request.args.get('risk_tier', '')
        payment = request.args.get('payment_method', '')
        category = request.args.get('category', '')
        city = request.args.get('city', '')

        where_clauses = []
        params = {}
        if payment:
            where_clauses.append("o.payment_method = :payment")
            params['payment'] = payment
        if category:
            where_clauses.append("p.category = :category")
            params['category'] = category
        if city:
            where_clauses.append("l.delivery_city = :city")
            params['city'] = city
        if risk_tier:
            where_clauses.append("op.risk_tier = :risk_tier")
            params['risk_tier'] = risk_tier

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        with get_db() as conn:
            result = conn.execute(text(f"""
                SELECT o.order_id, o.order_date, o.customer_id, p.product_name,
                       p.category, o.quantity, o.discount_percentage,
                       o.payment_method, l.courier_partner, l.delivery_city,
                       op.predicted_return_prob AS predicted_prob, r.is_returned, r.return_reason
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
                JOIN logistics l ON o.order_id = l.order_id
                JOIN returns r ON o.order_id = r.order_id
                LEFT JOIN order_predictions op ON o.order_id = op.order_id
                {where_sql}
                ORDER BY o.order_id
            """), params)
            rows = rows_to_dicts(result)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v is not None else '' for k, v in row.items()})

        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=orders_export.csv'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Customers API ─────────────────────────────────────────────────────────────
@app.route('/api/customers')
@login_required
def api_customers():
    try:
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        search = request.args.get('search', '')
        segment = request.args.get('segment', '')
        city = request.args.get('city', '')
        sort_by = request.args.get('sort_by', 'customer_id')

        allowed_sorts = {'customer_id', 'overall_return_rate', 'total_orders', 'avg_order_value'}
        if sort_by not in allowed_sorts:
            sort_by = 'customer_id'
        
        sort_dir = "ASC"  # User strictly specified all sorting should be explicitly ascending
        sort_col = sort_by
        if sort_by == 'customer_id':
            # Dynamically sort customer_id alphabetically or numerically by trimming the C
            sort_col = "TO_NUMBER(SUBSTR(customer_id, 2))"

        where_clauses = []
        params = {}

        if search:
            where_clauses.append("(c.customer_id LIKE :search OR c.city LIKE :search2)")
            params['search'] = f'%{search}%'
            params['search2'] = f'%{search}%'
        if city:
            where_clauses.append("c.city = :city")
            params['city'] = city
            
        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        having_clause = ""
        if segment == 'zero':
            having_clause = "HAVING CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END = 0"
        elif segment == 'low':
            having_clause = "HAVING CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END > 0 AND CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END <= 0.10"
        elif segment == 'medium':
            having_clause = "HAVING CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END > 0.10 AND CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END <= 0.25"
        elif segment == 'high':
            having_clause = "HAVING CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END > 0.25"

        base_query = f"""
            SELECT c.customer_id, c.city, c.state, c.pincode, c.customer_tenure_days, c.avg_days_between_orders, c.last_order_days_ago, c.frequent_return_flag,
                   COUNT(o.order_id) AS total_orders,
                   NVL(SUM(r.is_returned), 0) AS total_returns,
                   CASE WHEN COUNT(o.order_id) > 0 THEN NVL(SUM(r.is_returned), 0) / COUNT(o.order_id) ELSE 0 END AS overall_return_rate,
                   NVL(AVG(o.final_price), 0) AS avg_order_value
            FROM customers c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
            LEFT JOIN returns r ON o.order_id = r.order_id
            {where_sql}
            GROUP BY c.customer_id, c.city, c.state, c.pincode, c.customer_tenure_days, c.avg_days_between_orders, c.last_order_days_ago, c.frequent_return_flag
            {having_clause}
        """

        with get_db() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM ({base_query})"), params)
            total = count_result.scalar()

            result = conn.execute(text(f"""
                SELECT * FROM (
                    SELECT q.*, ROWNUM rn FROM (
                        {base_query} ORDER BY {sort_col} {sort_dir}
                    ) q WHERE ROWNUM <= :end_row
                ) WHERE rn > :start_row
            """), {**params, 'end_row': page * per_page, 'start_row': offset})
            rows = rows_to_dicts(result)

        # Apply segment purely based on dynamic mathematical rates
        for row in rows:
            rate = float(row.get('overall_return_rate') or 0)
            if rate == 0:
                row['segment'] = 'Zero'
            elif rate <= 0.10:
                row['segment'] = 'Low'
            elif rate <= 0.25:
                row['segment'] = 'Medium'
            else:
                row['segment'] = 'High'

        return jsonify({'rows': rows, 'total': total, 'page': page, 'per_page': per_page})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/customers/<customer_id>')
@login_required
def api_customer_detail(customer_id):
    try:
        with get_db() as conn:
            cr = conn.execute(text("SELECT * FROM customers WHERE customer_id = :id"), {'id': customer_id})
            customer = rows_to_dicts(cr)
            if not customer:
                return jsonify({'error': 'Not found'}), 404
            customer = customer[0]

            # Order history computation for single truth source
            ordr = conn.execute(text("""
                SELECT o.order_id, o.order_date, o.quantity, o.discount_percentage,
                       o.payment_method, p.product_name, p.category,
                       r.is_returned, r.return_reason
                FROM orders o
                JOIN products p ON o.product_id = p.product_id
                JOIN returns r ON o.order_id = r.order_id
                WHERE o.customer_id = :id
                ORDER BY TO_NUMBER(SUBSTR(o.order_id, 2)) ASC
            """), {'id': customer_id})
            order_history = rows_to_dicts(ordr)
            
            # Form truth validations mathematically from exact tuples
            from collections import Counter
            total_history_orders = len(order_history)
            total_history_returns = sum(1 for x in order_history if x['is_returned'])
            customer['total_orders'] = total_history_orders
            customer['total_returns'] = total_history_returns
            customer['overall_return_rate'] = (total_history_returns / total_history_orders) if total_history_orders > 0 else 0
            
            cats = [x['category'] for x in order_history]
            customer['preferred_category'] = Counter(cats).most_common(1)[0][0] if cats else 'N/A'
            
            for row in order_history:
                if row.get('order_date'):
                    d = str(row['order_date'])[:10]
                    row['order_date'] = f"{d[8:10]}-{d[5:7]}-{d[0:4]}" if len(d) == 10 else d

            # Dynamic Graphing Structure: No. of returns per Category -> Sub Products Dictionaries
            cat_product_returns = {}
            for o in order_history:
                if o['is_returned']:
                    c = o['category']
                    p = o['product_name']
                    if c not in cat_product_returns:
                        cat_product_returns[c] = {}
                    cat_product_returns[c][p] = cat_product_returns[c].get(p, 0) + 1
                    
            cat_returns_list = [{'category': c, 'returns': sum(v.values()), 'products': v} for c, v in cat_product_returns.items()]

            # Return reason breakdown
            rr = conn.execute(text("""
                SELECT r.return_reason, COUNT(*) AS cnt
                FROM returns r
                JOIN orders o ON r.order_id = o.order_id
                WHERE o.customer_id = :id AND r.is_returned = 1
                GROUP BY r.return_reason
            """), {'id': customer_id})
            return_reasons = rows_to_dicts(rr)

            # Predictions
            preds = conn.execute(text("""
                SELECT op.order_id, p.product_name, op.risk_tier,
                       op.predicted_return_prob AS predicted_prob, op.predicted_at AS prediction_date,
                       r.is_returned
                FROM order_predictions op
                JOIN products p ON op.product_id = p.product_id
                LEFT JOIN returns r ON op.order_id = r.order_id
                WHERE op.customer_id = :id
                ORDER BY op.predicted_at DESC
            """), {'id': customer_id})
            predictions = rows_to_dicts(preds)
            for p in predictions:
                predicted_high = 'Require' in p.get('risk_tier', '') or 'Block' in p.get('risk_tier', '') or 'Restrict' in p.get('risk_tier', '')
                actual_returned = p.get('is_returned')
                
                if actual_returned is None:
                    p['correct'] = 'N/A' # Simulated records do not have actual outcomes
                    p['actual_shipped'] = 'Simulation Log'
                else:
                    p['correct'] = predicted_high == bool(actual_returned)
                    p['actual_shipped'] = 'Yes' if actual_returned else 'No'

                p['predicted_pct'] = round(float(p['predicted_prob']) * 100, 1) if p.get('predicted_prob') else None
                if p.get('prediction_date'):
                    d = str(p['prediction_date'])[:10]
                    p['prediction_date'] = f"{d[8:10]}-{d[5:7]}-{d[0:4]}" if len(d) == 10 else d

        return jsonify({
            'customer': customer,
            'order_history': order_history,
            'return_reasons': return_reasons,
            'category_returns': cat_returns_list,
            'predictions': predictions
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

# ─── Save Prediction ────────────────────────────────────────────────────────────
@app.route('/api/save-prediction', methods=['POST'])
@login_required
def api_save_prediction():
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        product_id = data.get('product_id')
        order_id = data.get('order_id')
        predicted_prob = data.get('predicted_prob')
        risk_tier = data.get('risk_tier')
        top_drivers = data.get('top_drivers', [])

        d1 = top_drivers[0]['feature'] if len(top_drivers) > 0 else None
        d2 = top_drivers[1]['feature'] if len(top_drivers) > 1 else None
        d3 = top_drivers[2]['feature'] if len(top_drivers) > 2 else None

        with get_db() as conn:
            conn.execute(text("""
                MERGE INTO order_predictions op
                USING DUAL ON (op.order_id = :order_id)
                WHEN MATCHED THEN
                    UPDATE SET predicted_return_prob = :prob, risk_tier = :tier,
                               predicted_at = SYSDATE,
                               top_driver_1 = :d1, top_driver_2 = :d2, top_driver_3 = :d3,
                               customer_id = :customer_id, product_id = :product_id
                WHEN NOT MATCHED THEN
                    INSERT (order_id, customer_id, product_id, predicted_return_prob, risk_tier, predicted_at,
                            top_driver_1, top_driver_2, top_driver_3)
                    VALUES (:order_id, :customer_id, :product_id, :prob, :tier, SYSDATE, :d1, :d2, :d3)
            """), {
                'order_id': order_id, 'customer_id': customer_id, 'product_id': product_id,
                'prob': predicted_prob, 'tier': risk_tier,
                'd1': d1, 'd2': d2, 'd3': d3
            })
            conn.commit()

        return jsonify({'success': True, 'message': 'Prediction saved to Oracle'})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 500}), 500

@app.route('/api/model-report')
@login_required
def api_model_report():
    return jsonify(model_report)

if __name__ == '__main__':
    app.run(debug=True, port=5000)