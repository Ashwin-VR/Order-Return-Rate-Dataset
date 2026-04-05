# 🇧🇷 External Dataset Test Report: Olist (Real Mode)

## 🎯 Overview
This report validates the robustness of our data pipeline by running the Brazilian e-commerce public dataset (`olist.sqlite`) through our universal `sql_dataset_adapter.py` and the core `preprocess.py` pipeline utilizing the **Dual-Pipeline Architecture (Mode A: Real)**.

---

## 📋 Data Transformation Journey

1. **Raw External Source**: `D:\coding_stuffs\minor_project_supply_chain\Order-Return-Rate-Dataset\data\external_olist_mapped.csv` (10,000 rows mapped via SQL JOIN across 6 tables)
2. **Schema Adapter**: `scripts/sql_dataset_adapter.py` mapped existing review features (`review_score`, `review_comment_message`, `order_purchase_timestamp`) and generated synthetic logistics defaults just to support Phase 0 validation. 
## 📉 Preprocessing Metrics

* **Original Rows**: 10,000
* **Preprocessed Rows**: 10000
* **Columns Generated**: 72 features (Strictly ignoring leaked synthetic dimensions)
* **Overall Return Count (Redesigned Real Target)**: 1353 (13.53%)
* **Sarcasm Detections (Mathematical Model)**: 387  
* **Spam/Low-Effort Detections**: 0

---

## ✅ Pipeline Compatibility Checklist

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Adapter Mapping** | Safely map complex relational SQLite to SQL-like CSV schema | ✅ Pass |
| **Phase 0** | Schema Standardization | ✅ Pass |
| **Phase 1** | Handling Returns & Integrity (Missing values handled) | ✅ Pass |
| **Phase 2** | Temporal Extraction | ✅ Pass |
| **Phase 3** | Behavioral & Rolling Windows | ✅ Pass |
| **Phase 4** | NLP, Sarcasm & Spam Scoring (True metrics only) | ✅ Pass |
| **Phase 5** | Target Encoding & Scaling (Synthetic features dropped entirely) | ✅ Pass |

## 💡 Conclusion
The generalized preprocessing pipeline successfully ingested complex, real-world, Portuguese-language domain data (`Olist Orders`) without fatal errors in **Real Mode**. 
Based on the `pipeline_improvement_1.md` guidelines, the structural inputs correctly ignored synthesized variables, computing Sarcasm and Spam purely on mathematical rating/sentiment contradictions completely isolated from synthetic dependencies.

Our setup proves highly agnostic and adaptable to completely different dialects, locations (Brazil), and DB origins (SQLite) utilizing the current generalized pipeline.

*Generated on: April 03, 2026*
