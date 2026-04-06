import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import warnings

warnings.filterwarnings('ignore')

# Load all generated synthetic datasets
try:
    orders_df = pd.read_csv("orders.csv")
    customers_df = pd.read_csv("customers.csv")
    products_df = pd.read_csv("products.csv")
except FileNotFoundError:
    print("Please run data_generation.py first!")
    exit()

# Combine datasets if not already combined
if "persona" not in orders_df.columns:
    df = orders_df.merge(customers_df, on="customer_id", how="left").merge(products_df, on="product_id", how="left")
else:
    df = orders_df

df.to_csv("final_combined_data.csv", index=False)

print("========================================")
print("      EXPLORATORY DATA ANALYSIS")
print("========================================")
print(f"Combined Dataset Shape: {df.shape}")
print("\n--- Missing Values ---")
print(df.isnull().sum()[df.isnull().sum() > 0])
print("\n--- Summary Statistics (Target: return_probability) ---")
print(df['return_probability'].describe())
print("\n--- Average Return Probability by Persona (%) ---")
if 'persona' in df.columns:
    print(df.groupby('persona')['return_probability'].mean() * 100)
print("\n--- Average Return Probability by Category (%) ---")
if 'category' in df.columns:
    print(df.groupby('category')['return_probability'].mean() * 100)

print("\n========================================")
print("         MODEL EVALUATION METRICS")
print("========================================")

# Prepare Data
# Target variable is return_probability for regression
y = df["return_probability"]

# Drop identifiers, labels (we only want predictors for returning)
# is_returned is a direct proxy for probability so drop it
X = df.drop(columns=["order_id", "customer_id", "product_id", "order_date", "return_probability", "is_returned", "base_return_rate"], errors='ignore')

# Categorical mapping
X = pd.get_dummies(X, columns=["persona", "category"], drop_first=True)

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train a fast model
model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10, n_jobs=-1)
model.fit(X_train, y_train)

# Predict
y_pred_test = model.predict(X_test)
y_pred_train = model.predict(X_train)

# Calculate Metrics
r2_train = r2_score(y_train, y_pred_train)
r2_test = r2_score(y_test, y_pred_test)
rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
mae_test = mean_absolute_error(y_test, y_pred_test)

print(f"Train R-squared : {r2_train:.4f}")
print(f"Test R-squared  : {r2_test:.4f}")
print(f"Test RMSE       : {rmse_test:.4f}")
print(f"Test MAE        : {mae_test:.4f}")

# Feature Importances
print("\n--- Top 5 Important Features ---")
importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
print(importances.head(5))

