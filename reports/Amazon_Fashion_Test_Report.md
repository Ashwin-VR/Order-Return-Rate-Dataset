# 🛍️ External Dataset Test Report: Amazon Fashion

## 🎯 Overview
This report validates the robustness of our data pipeline by running an external real-world dataset (`AMAZON_FASHION.json`) through our `generic_dataset_adapter.py` and the core `preprocess.py` pipeline.

---

## 📋 Data Transformation Journey

1. **Raw External Source**: `external_amazon_fashion_mapped.csv` (10,000 rows mapped)
2. **Schema Adapter**: `scripts/generic_dataset_adapter.py` mapped existing review features (`reviewText`, `overall`, `unixReviewTime`) and generated synthetic logistics defaults.
3. **Pipeline Target**: `external_amazon_fashion_preprocessed.csv`

---

## 📉 Preprocessing Metrics

* **Original Rows**: 10,000
* **Preprocessed Rows**: 10000
* **Columns Generated**: 72 features (including scaled, Target Encoded, and Sarcasm/Spam features)
* **Overall Return Count**: 1159 (11.59%)
* **Sarcasm Detections (Mathematical Model)**: 184
* **Spam/Low-Effort Detections**: 0

---

## ✅ Pipeline Compatibility Checklist

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Adapter Mapping** | Safely map existing JSON to SQL-like CSV schema | ✅ Pass |
| **Phase 0** | Schema Standardization | ✅ Pass |
| **Phase 1** | Handling Returns & Integrity (Missing values handled) | ✅ Pass |
| **Phase 2** | Temporal Extraction | ✅ Pass |
| **Phase 3** | Behavioral & Rolling Windows | ✅ Pass |
| **Phase 4** | NLP, Sarcasm & Spam Scoring | ✅ Pass |
| **Phase 5** | Target Encoding & Scaling | ✅ Pass |

## 💡 Conclusion
The generalized preprocessing pipeline successfully ingested external domain data (`Amazon Fashion`) without fatal errors. The modular abstraction of standard structural inputs allowed mathematical contradiction rules (e.g. predicting sarcasm via delay vs sentiment metrics) to function seamlessly with an adapted, mapped real-world corpus.

*Generated on: April 03, 2026*
