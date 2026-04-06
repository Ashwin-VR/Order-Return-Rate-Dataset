import pandas as pd
import numpy as np
import os

# Adjust path to find data in parent directory if running from task/
data_files = [
    "final_combined_data.csv",
    "../final_combined_data.csv",
    "../../final_combined_data.csv"
]

df = None
for file_path in data_files:
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        print(f"✓ Loaded data from: {file_path}")
        break

if df is None:
    print("❌ Data not found. Did you run the data generation script?")
    print("Expected file: final_combined_data.csv (or run from final_moments/ directory)")
    exit()

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

section("1. DATASET OVERVIEW")
print(f"Shape: {df.shape}")
print(f"Duplicate Rows: {df.duplicated().sum()}")
numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
categorical_cols = df.select_dtypes(exclude=np.number).columns.tolist()
print(f"Numeric: {numeric_cols}")
print(f"Categorical: {categorical_cols}")

section("2. DATA QUALITY CHECKS")
print(f"Missing Values: \n{df.isnull().sum()[df.isnull().sum() > 0]}")
print(f"Return Prob Bound Check: Min={df['return_probability'].min():.2f}, Max={df['return_probability'].max():.2f}")

section("3. TARGET VARIABLE ANALYSIS")
print("return_probability Summary:")
print(df['return_probability'].describe())
print(f"\nSkewness: {df['return_probability'].skew():.4f}")
print("\nis_returned Distribution:")
print(df['is_returned'].value_counts(normalize=True) * 100)

section("4. CATEGORICAL FEATURE ANALYSIS")
for col in ['persona', 'category', 'is_holiday_season']:
    print(f"\n--- {col.upper()} ---")
    summary = df.groupby(col).agg(
        Count=('return_probability', 'count'),
        Avg_Return_Prob=('return_probability', 'mean'),
        Return_Rate_Pct=('is_returned', 'mean')
    )
    summary['Avg_Return_Prob'] = (summary['Avg_Return_Prob'] * 100).round(2)
    summary['Return_Rate_Pct'] = (summary['Return_Rate_Pct'] * 100).round(2)
    print(summary)


section("5. FEATURE RELATIONSHIPS (Deterministic Rules Check)")
print("\nRule 1: Apparel/Footwear + High Delay (>3) -> Surge in Probability")
rule1 = df[(df['category'].isin(['Apparel', 'Footwear'])) & (df['delivery_delay'] > 3)]
control1 = df[(df['category'].isin(['Apparel', 'Footwear'])) & (df['delivery_delay'] <= 3)]
print(f"Avg Return Prob (High Delay): {rule1['return_probability'].mean()*100:.2f}%")
print(f"Avg Return Prob (Low Delay) : {control1['return_probability'].mean()*100:.2f}%")

print("\nRule 2: Electronics + High Delay (>2) -> Small Penalty")
rule2 = df[(df['category'] == 'Electronics') & (df['delivery_delay'] > 2)]
control2 = df[(df['category'] == 'Electronics') & (df['delivery_delay'] <= 2)]
print(f"Avg Return Prob (Electronics High Delay): {rule2['return_probability'].mean()*100:.2f}%")
print(f"Avg Return Prob (Electronics Low Delay) : {control2['return_probability'].mean()*100:.2f}%")

print("\nRule 3: Low Rating (<3.0) -> Exponential Surge")
rule3 = df[df['rating'] < 3.0]
control3 = df[df['rating'] >= 3.0]
print(f"Avg Return Prob (Rating < 3.0): {rule3['return_probability'].mean()*100:.2f}%")
print(f"Avg Return Prob (Rating >= 3.0) : {control3['return_probability'].mean()*100:.2f}%")

print("\nRule 4: Holiday + Impulse Buyer")
rule4 = df[(df['is_holiday_season'] == 1) & (df['persona'] == 'Impulse Buyer')]
control4 = df[(df['is_holiday_season'] == 0) & (df['persona'] == 'Impulse Buyer')]
print(f"Avg Return Prob (Holiday Impulse): {rule4['return_probability'].mean()*100:.2f}%")
print(f"Avg Return Prob (Normal Impulse) : {control4['return_probability'].mean()*100:.2f}%")

section("6. LINEAR CORRELATIONS")
corrs = df[numeric_cols].corr()['return_probability'].sort_values(ascending=False)
print(corrs.round(3))
