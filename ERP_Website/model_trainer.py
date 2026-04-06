import pandas as pd
import numpy as np
import joblib
import json
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from imblearn.over_sampling import SMOTE
import warnings

warnings.filterwarnings('ignore')

def train_model():
    print("Loading Dataset...")
    df = pd.read_csv('data/final_combined_data.csv')
    df['order_date'] = pd.to_datetime(df['order_date'])
    df = df.sort_values('order_date').reset_index(drop=True)

    leakage_cols = ['overall_return_rate', 'total_returns', 'frequent_return_flag', 'product_return_rate', 'category_return_rate']
    drop_cols = ['order_id', 'product_id', 'product_name']

    cols_to_drop = [c for c in drop_cols if c in df.columns]
    df_clean = df.drop(columns=cols_to_drop)

    df_clean['delivery_delay'] = np.clip(df_clean['delivery_delay'], a_min=-5, a_max=15)
    df_clean['high_value_delayed'] = df_clean['final_price'] * df_clean['delivery_delay']

    cat_columns = df_clean.select_dtypes(include=['object', 'bool']).columns.tolist()
    cat_columns = [c for c in cat_columns if c not in ['customer_id', 'order_date']]
    df_encoded = pd.get_dummies(df_clean, columns=cat_columns, drop_first=True)

    leakage_cols_present = [c for c in leakage_cols if c in df_encoded.columns]
    features_to_drop = ['is_returned', 'customer_id', 'order_date', 'return_days_after_delivery'] + [c for c in df_encoded.columns if 'return_reason' in c] + leakage_cols_present

    X = df_encoded.drop(columns=features_to_drop, errors='ignore')
    y = df_encoded['is_returned']

    print(f"Features mapped: {len(X.columns)}")

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=df_encoded['customer_id']))

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)

    print("Fitting RF Classifier & Calibrated CV...")
    rf_base = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    model = CalibratedClassifierCV(estimator=rf_base, cv=3, method='isotonic')
    model.fit(X_train_resampled, y_train_resampled)

    rf_base.fit(X_train_resampled, y_train_resampled)
    importances = pd.DataFrame({'feature': X.columns, 'importance': rf_base.feature_importances_})
    importances = importances.sort_values('importance', ascending=False)
    
    with open('feature_importance.json', 'w') as f:
        f.write(importances.head(15).to_json(orient='records'))

    joblib.dump(model, 'model.pkl')
    joblib.dump(scaler, 'scaler.pkl')
    joblib.dump(X.columns.tolist(), 'feature_columns.pkl')

    print("✅ Model logic ported, trained, and saved perfectly.")

_model = None
_feature_cols = None
_scaler = None

def _load_artifacts():
    global _model, _feature_cols, _scaler
    if _model is None:
        _model = joblib.load('model.pkl')
    if _feature_cols is None:
        _feature_cols = joblib.load('feature_columns.pkl')
    if _scaler is None:
        try:
            _scaler = joblib.load('scaler.pkl')
        except:
            _scaler = None

def decision_engine_tier(prob, historical_return_rate, is_frequent):
    if prob < 0.20:
        return "Allow Order"
    elif 0.20 <= prob < 0.50:
        if historical_return_rate <= 0.15 and not is_frequent:
             return "Allow Order (Loyal)"
        return "Restrict Discounts"
    elif 0.50 <= prob < 0.75:
        if is_frequent:
             return "Require Prepayment"
        return "Standard Shipping Only"
    else:
        return "Block COD"

def predict_single(order_dict):
    _load_artifacts()

    # Preprocess identically to notebook
    df_single = pd.DataFrame([order_dict])
    
    # We substitute expected_delivery_days for delivery_delay purely to calculate interaction during inference context before actual reality happens
    sim_delay = df_single['expected_delivery_days'].values[0] if 'expected_delivery_days' in df_single else 3
    df_single['high_value_delayed'] = df_single['final_price'] * np.clip(sim_delay, -5, 15)
    
    encoded = pd.get_dummies(df_single)
    encoded = encoded.reindex(columns=_feature_cols, fill_value=0)
    
    X_input = encoded.values
    if _scaler is not None:
        X_input = _scaler.transform(encoded)
        
    prob = _model.predict_proba(X_input)[0, 1]
    
    is_frequent = order_dict.get('frequent_return_flag', 0) == 1
    historic = order_dict.get('overall_return_rate', 0)
    
    tier = decision_engine_tier(prob, historic, is_frequent)
    
    return {
        'predicted_prob': float(prob),
        'risk_tier': tier
    }

if __name__ == '__main__':
    train_model()
