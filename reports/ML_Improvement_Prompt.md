# 🛠️ ML Model Improvement Prompt — Order Return Rate Prediction System

> **Purpose**: This document is a structured prompt/brief for implementing improvements to the machine learning pipeline in this repository. It is derived from a full audit of all model code, preprocessing scripts, and performance reports. Reference files and line numbers are included for every issue. Work through each section in order.

---

## 📋 Context

The system has four core XGBoost models trained in `scripts/train_core_predictors.py`, a 5-phase preprocessing pipeline in `preprocessing/preprocess.py`, and two auxiliary text classifiers in `scripts/train_ml_classifiers.py`. The training data is a synthetic 5,000-row e-commerce dataset (`data/synthetic_ecommerce_orders.csv`).

**Reported performance (from `reports/Core_Predictors_Report.md`)**:

| Model | Target | Algorithm | Key Metric |
|---|---|---|---|
| Return Predictor | `is_returned` | XGBClassifier | Accuracy 62%, AUC 0.61 |
| Delay Forecaster | `delivery_delay` | XGBRegressor | RMSE 1.45 days, **R² −0.049** |
| CSAT Predictor | `review_rating` | XGBRegressor | RMSE 0.94 stars, R² 0.58 |
| Revenue Predictor | `order_value` | XGBRegressor | RMSE $53.90, R² 0.9994 |

---

## 🔴 Priority 1 — Critical Bugs (Fix These First)

### 1.1 Look-ahead Bias in `is_high_risk_product`

**File**: `preprocessing/preprocess.py`, line 285
**Issue**: `transform('mean')` aggregates across all rows for each `product_id`, including future orders. This leaks future return information into past records.

```python
# CURRENT (leaky):
product_return_rates = df.groupby('product_id')['is_returned'].transform('mean')
df['is_high_risk_product'] = (product_return_rates > defect_threshold).astype(int)
```

**Fix**: Use a time-aware expanding mean with a one-step shift, exactly as `prod_category_return_rate` is already done correctly at line 279:

```python
# CORRECT (time-aware, no look-ahead):
df = df.sort_values('order_date')
df['is_high_risk_product'] = (
    df.groupby('product_id')['is_returned']
      .transform(lambda x: x.expanding().mean().shift(1).fillna(0.0))
    > defect_threshold
).astype(int)
```

---

### 1.2 Target Encoding Applied to the Full Dataset (Test-Set Leakage)

**File**: `preprocessing/preprocess.py`, lines 494–520 (`encode_categorical_features`)
**Issue**: Target encoding is computed over the full DataFrame, so the test-set's return rates influence the encoded values seen during training.

**Fix**: Compute target encoding **only on the training fold** and apply the learned mapping to the validation/test fold. In the pipeline context, wrap target encoding inside a `sklearn`-compatible transformer so it fits only on `X_train`:

```python
# Use category_encoders library (pip install category_encoders)
from category_encoders import TargetEncoder
encoder = TargetEncoder(cols=categorical_cols, smoothing=1.0)
X_train[categorical_cols] = encoder.fit_transform(X_train[categorical_cols], y_train)
X_test[categorical_cols]  = encoder.transform(X_test[categorical_cols])
```

Alternatively, use a cross-validated target-encoding scheme (e.g., 5-fold OOF encoding) before the final split.

---

### 1.3 Circular Pseudo-Labels in Sarcasm & Spam Classifiers

**File**: `scripts/train_ml_classifiers.py`, lines 37–65
**Issue**: The ML classifiers are trained on labels (`is_sarcastic_score_flag`, `is_likely_spam`) that are themselves produced by the heuristic scoring functions in `preprocess.py`. The classifier therefore learns a perfect bijection of the heuristic — not genuine sarcasm or spam. This is confirmed by the 100% accuracy reported in `reports/Sarcasm_Spam_ML_Report.md` (line 28).

**Fix options (pick one)**:
- **Option A (preferred)**: Remove the ML classifier layer entirely. Use the heuristic scores (`sarcasm_score`, `spam_score`) directly as features in downstream models. Do not wrap them in a second ML model.
- **Option B**: Manually annotate 300–500 reviews with genuine sarcasm/spam labels (recommended in `reports/Synthetic_Data_Quality_Report.md`, line 102) and retrain on those ground-truth labels.

---

### 1.4 Invalid `review_rating` Imputation

**File**: `preprocessing/preprocess.py`, line 103
**Issue**: Missing `review_rating` is imputed with `0`. This value is outside the valid 1–5 range and creates a phantom class that distorts all downstream models using this feature (CSAT predictor, sarcasm scoring).

```python
# CURRENT (wrong):
df['review_rating'] = df['review_rating'].fillna(0)
```

**Fix**: Impute with median (≈3.0 for this dataset) and preserve the `has_review` flag to distinguish imputed from real ratings:

```python
# CORRECT:
median_rating = df.loc[df['review_rating'].notna(), 'review_rating'].median()
df['review_rating'] = df['review_rating'].fillna(median_rating)
# has_review flag already created at line 100, keep it
```

---

## 🟠 Priority 2 — Model Quality Improvements

### 2.1 Return Predictor: Use Cross-Validation in Hyperparameter Tuning Objective

**File**: `scripts/train_core_predictors.py`, lines 84–108
**Issue**: The Optuna objective function (line 107) evaluates F1 on a fixed test split. This makes hyperparameter selection dependent on a single 20% holdout — high variance with only ~1,000 test samples.

**Fix**: Replace single-split evaluation with 3-fold CV inside the objective:

```python
from sklearn.model_selection import cross_val_score, StratifiedKFold

def objective(trial):
    params = { ... }  # same as current
    pipe = Pipeline(steps=[('preprocessor', preprocessor), ('model', XGBClassifier(**params))])
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='f1')
    return scores.mean()
```

Also expand the Optuna search space (currently lines 86–95) to include regularization parameters:

```python
'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
'gamma':            trial.suggest_float('gamma', 0, 5),
'reg_alpha':        trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
'reg_lambda':       trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
```

Increase `n_trials` from 10 (line 111) to at least 50.

---

### 2.2 Delivery Delay Forecaster: Predict a Distribution, Not a Point

**File**: `scripts/train_core_predictors.py`, lines 146–206
**Issue**: R² = −0.049 means the model is worse than predicting the mean. A point-estimate regressor has no signal when delays are quasi-random.

**Fix (two-step)**:

**Step 1** — Fix the synthetic data to have a tighter delay signal. In `synthetic_data_generation.py`, strengthen the `distance_km` → `delivery_delay` relationship so that correlation exceeds 0.5 (current EDA shows only 0.296 per `reports/EDA_Report.md`, line 44).

**Step 2** — Predict a quantile (P50) instead of mean, and add P10/P90 bounds for uncertainty:

```python
from sklearn.ensemble import GradientBoostingRegressor

# Train three models: low, median, high
for alpha in [0.1, 0.5, 0.9]:
    model = GradientBoostingRegressor(loss='quantile', alpha=alpha, n_estimators=200)
    model.fit(X_train, y_train)
```

This yields actionable business output: "This order has a 90% chance of arriving within X days."

---

### 2.3 CSAT Predictor: Treat Rating as Ordinal, Not Continuous

**File**: `scripts/train_core_predictors.py`, lines 208–240
**Issue**: `review_rating` (1–5 stars) is modeled as a continuous regression target. Predicting 2.7 "between" stars is meaningless; the ordinal structure (1 < 2 < 3 < 4 < 5) is ignored.

**Fix option A** — Reframe as 5-class classification:

```python
from sklearn.metrics import cohen_kappa_score  # weighted kappa for ordinal

pipeline = build_pipeline(num_features, cat_features, is_classification=True)
# Encode y as integers 0–4 (rating - 1)
y_encoded = (y - 1).astype(int)
pipeline.fit(X_train, y_encoded)
y_pred = pipeline.predict(X_test) + 1
print("Weighted Kappa:", cohen_kappa_score(y_test, y_pred, weights='quadratic'))
```

**Fix option B** — Use ordinal regression (`pip install mord`):

```python
import mord
model = mord.LogisticAT()  # proportional odds / cumulative link
model.fit(X_train_transformed, y_train)
```

**New evaluation metrics to add**:
- Exact-match accuracy (predicted star = actual star)
- Adjacent accuracy (within ±1 star)
- Quadratic-weighted Cohen's Kappa (standard metric for ordinal rating tasks)

---

### 2.4 Revenue Model: Remove or Reframe

**File**: `scripts/train_core_predictors.py`, lines 242–270
**Issue**: R² = 0.9994 because the model learns the trivial identity `order_value = product_price × quantity`. It provides no real prediction value.

**Fix options**:
- **Remove** the model from the pipeline if the only use is financial verification (use arithmetic directly).
- **Reframe** the target as something non-trivial: e.g., predict `net_revenue_after_returns = order_value × (1 − P(is_returned))` by combining the revenue and return predictor outputs.

---

### 2.5 Add Missing Evaluation Metrics

**File**: `scripts/train_core_predictors.py`, lines 132–140 (Return Predictor metrics)

The following metrics must be added to `metrics` dict for each model:

**Return Predictor** (classification):
```python
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix

metrics["pr_auc"]       = float(average_precision_score(y_test, y_proba))
metrics["brier_score"]  = float(brier_score_loss(y_test, y_proba))
metrics["precision"]    = float(precision_score(y_test, y_pred))
tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
metrics["confusion_matrix"] = {"TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn)}
```

**Delay Forecaster** (regression):
```python
from sklearn.metrics import mean_absolute_error

metrics["mae_days"]    = float(mean_absolute_error(y_test, y_pred))
metrics["within_1day"] = float((np.abs(y_test - y_pred) <= 1).mean())
```

**CSAT Predictor** (ordinal):
```python
from scipy.stats import spearmanr

metrics["spearman_r"] = float(spearmanr(y_test, y_pred).correlation)
metrics["exact_match"] = float((np.round(y_pred) == y_test).mean())
```

---

## 🟡 Priority 3 — Feature Engineering Enhancements

### 3.1 Encode Cyclical Time Features with Sin/Cos

**File**: `preprocessing/preprocess.py`, lines 189–193
**Issue**: Hour, day-of-week, and month are passed as raw integers. The model treats hour 23 and hour 0 as maximally different, despite being adjacent.

**Fix**: Add cyclical encoding alongside the raw integer (keep both for tree models):

```python
# After extracting order_hour, order_day_of_week, order_month:
df['order_hour_sin'] = np.sin(2 * np.pi * df['order_hour'] / 24)
df['order_hour_cos'] = np.cos(2 * np.pi * df['order_hour'] / 24)

df['order_dow_sin']  = np.sin(2 * np.pi * df['order_day_of_week'] / 7)
df['order_dow_cos']  = np.cos(2 * np.pi * df['order_day_of_week'] / 7)

df['order_month_sin'] = np.sin(2 * np.pi * df['order_month'] / 12)
df['order_month_cos'] = np.cos(2 * np.pi * df['order_month'] / 12)
```

---

### 3.2 Add Risk Interaction Features for Return Predictor

**File**: `scripts/train_core_predictors.py`, line 67 (num_features list)
**Motivation**: `base_return_tendency` (11.3% importance) and `discount_percentage` (9.8%) are top drivers. Their interaction captures "impulse buyers who also return often."

**Add these derived features before the train-test split**:

```python
df['discount_x_return_tendency'] = df['discount_percentage'] * df['base_return_tendency']
df['defect_x_distance']          = df['defect_rate'] * df['distance_km']
df['high_discount_flag']         = (df['discount_percentage'] > 0.40).astype(int)

# Add to num_features list:
num_features = [
    'discount_percentage', 'distance_km', 'past_return_rate',
    'base_return_tendency', 'defect_rate', 'delivery_delay',
    'discount_x_return_tendency', 'defect_x_distance', 'high_discount_flag'
]
```

---

### 3.3 Consider CatBoost as an Alternative Algorithm

**File**: `scripts/train_core_predictors.py`, lines 53–54
**Motivation**: The Return Predictor currently applies OneHotEncoding to `product_category`, `shipping_mode`, and `is_remote_area`. CatBoost handles categoricals natively using ordered target statistics, which is inherently resistant to the same leakage problem as target encoding.

```python
# pip install catboost
from catboost import CatBoostClassifier

cat_feature_indices = list(range(len(num_features), len(num_features) + len(cat_features)))
model = CatBoostClassifier(
    iterations=300,
    depth=6,
    learning_rate=0.05,
    cat_features=cat_feature_indices,
    auto_class_weights='Balanced',
    eval_metric='AUC',
    random_seed=42,
    verbose=0
)
```

---

### 3.4 Integrate Real-World Datasets for Generalization

**Files**: `reports/Olist_Test_Report.md`, `reports/Amazon_Fashion_Test_Report.md`
**Issue**: The synthetic data has delivery_delay → return correlations of 0.887 (per `reports/EDA_Report.md`, line 32), far above real-world levels (~0.2–0.3). Models trained on this will not generalize.

**Action**: Use the Olist and Amazon Fashion pipelines (already validated) as the primary training data. Treat synthetic data as a pre-training/augmentation source only. Add a domain-adaptation step (e.g., reweighting training samples by feature distribution similarity to real-world data).

---

## ✅ Improvement Checklist

Use this checklist to track implementation progress:

- [ ] **[P1.1]** Fix `is_high_risk_product` look-ahead bias (`preprocess.py:285`)
- [ ] **[P1.2]** Move target encoding inside CV folds (`preprocess.py:494–520`)
- [ ] **[P1.3]** Remove or replace circular sarcasm/spam ML classifiers (`train_ml_classifiers.py`)
- [ ] **[P1.4]** Fix `review_rating` imputation from `0` to median (`preprocess.py:103`)
- [ ] **[P2.1]** Add 3-fold CV + expanded search space to Optuna Return Predictor tuning (`train_core_predictors.py:84–118`)
- [ ] **[P2.2]** Replace point-estimate Delay Forecaster with quantile regression (`train_core_predictors.py:146–206`)
- [ ] **[P2.3]** Reframe CSAT as ordinal classification; add Kappa metric (`train_core_predictors.py:208–240`)
- [ ] **[P2.4]** Remove or reframe trivial Revenue model (`train_core_predictors.py:242–270`)
- [ ] **[P2.5]** Add PR-AUC, Brier score, MAE, Spearman R to metrics (`train_core_predictors.py:132–140`)
- [ ] **[P3.1]** Add sin/cos cyclical encoding for hour/day/month (`preprocess.py:189–193`)
- [ ] **[P3.2]** Add interaction features to Return Predictor feature list (`train_core_predictors.py:67`)
- [ ] **[P3.3]** Benchmark CatBoost vs XGBoost for Return Predictor (`train_core_predictors.py:53–54`)
- [ ] **[P3.4]** Integrate Olist / Amazon Fashion as real training data

---

## 📚 Reference Files

| File | Role |
|---|---|
| `preprocessing/preprocess.py` | 5-phase feature engineering pipeline |
| `scripts/train_core_predictors.py` | Core XGBoost model training (all 4 models) |
| `scripts/train_ml_classifiers.py` | Sarcasm & Spam text classifiers |
| `scripts/insights_extractor.py` | Feature importance & SHAP export |
| `reports/Core_Predictors_Report.md` | Performance metrics for all 4 models |
| `reports/PREPROCESSING_REPORT.md` | Preprocessing output, feature inventory |
| `reports/Automated_Insights_Report.md` | Feature importance business narrative |
| `reports/EDA_Report.md` | Correlation analysis, data integrity |
| `reports/Synthetic_Data_Quality_Report.md` | Synthetic data validation & known issues |
| `reports/Sarcasm_Spam_ML_Report.md` | Text classifier training report |
| `reports/Olist_Test_Report.md` | Real-world Olist pipeline test |
| `reports/Amazon_Fashion_Test_Report.md` | Real-world Amazon Fashion pipeline test |
| `data/synthetic_ecommerce_orders.csv` | Primary training dataset (5,000 rows, 29 cols) |
| `pipeline.py` | End-to-end pipeline orchestrator |

---

*Generated from full code and report audit — April 2026*
