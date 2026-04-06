# 📊 Business Decision Engine Report

## 1. Overview & Architecture
This report outlines the **Return Probability Predictive Engine** and its corresponding **Rule-Based Decision Layer** integrated into our supply chain and e-commerce pipeline.

The core architecture strictly separates **Predictive Machine Learning** from **Operational Business Logic**:
* **Machine Learning Model:** Evaluates a multi-domain dataset to output a continuous **Return Risk Score (Probability ranging from 0.0 to 1.0)**. It does *not* make business decisions autonomously.
* **Decision Engine:** Applies a dynamic, rules-based framework over the predicted probabilities. It dictates the final downstream actions to take on an order, balancing cost prevention with customer satisfaction.

---

## 2. Model Predictability & Baseline Signals
The system utilizes a Random Forest Regressor trained on the engineered dataset representing product, customer, and logistics components. 
* **Target Variable:** `return_probability` derived from the synthetic base `is_returned` ground truth.
* **Predictive Value Achieved:** The model successfully learns the nuanced relationships, verified with positive validation metrics ensuring operational reliability.

*(For full statistical breakdowns such as RMSE, MAE, and $R^2$ Variance Explained, refer to `reports/EDA_Insights_Report.md` and the exploratory notebooks in the `notebooks/` directory).*

---

## 3. Dynamic Rule-Based Actions Framework
The core business intervention applies varying degrees of friction based directly on the predicted **Return Risk Score**. Overrides are injected based on verified historical user behaviors (`overall_return_rate` and `frequent_return_flag`) to personalize the transaction.

### Tier 1: Low Risk
**Condition:** `probability < 0.20`
* **Action:** ✅ **Allow Order - No Action Needed**
* **Rationale:** Safe transaction baseline. Proceed with optimal shipping execution.

### Tier 2: Medium Risk
**Condition:** `0.20 ≤ probability < 0.50`
* **Default Action:** ⚠️ **Restrict Discounts / Show Return Warning**
* **Behavioral Override:** If historical return rate $\le 15\%$ and the user is NOT a frequent returner, downgrade the penalty.
  * *Override Action:* ✅ **Allow Order - Loyal Override**
* **Rationale:** Protect margins on potentially uncertain orders without unduly punishing long-term reliable customers.

### Tier 3: High Risk
**Condition:** `0.50 ≤ probability < 0.75`
* **Default Action:** 🚚 **Avoid Expedited Shipping (Standard Only) / Require Order Verification**
* **Behavioral Override:** If the user is flagged as a Frequent Returner.
  * *Override Action:* ❌ **Block COD / Require Prepayment (Frequent Returner Escalation)**
* **Rationale:** Minimize expensive fast-logistics losses. Escalate abusive accounts directly to pre-payment structures to confirm intent.

### Tier 4: Critical Risk
**Condition:** `probability ≥ 0.75`
* **Action:** ❌ **Block COD / Require Full Prepayment**
* **Rationale:** Absolute loss prevention. Ensure the cash-flow is secured before deploying warehouse or shipping resources.

---

## 4. Business Impact Summary
By layering structured rules over continuous ML probabilities, this logic achieves three core goals:
1. **Reduces Reverse Logistics Overhead:** Targets friction specifically onto the $ \ge 50\% $ risk bands, cutting predictable supply chain waste.
2. **Defends Healthy Customers:** Preserves seamless UX for the top tier and utilizes data overrides to protect occasional flukes from loyal buyers.
3. **Improves Cash Flow Security:** Shifting ultra-high-risk profiles ( $> 75\% $ ) entirely away from Cash-on-Delivery reduces dead-stock transit times and failed delivery costs.
