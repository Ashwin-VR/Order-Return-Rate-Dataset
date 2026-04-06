<h1 align="center">
  📦 ERP Data Pipeline & Order Return Predictor
</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Flask-Web_App-lightgrey.svg">
  <img src="https://img.shields.io/badge/Oracle-Database-red.svg">
  <img src="https://img.shields.io/badge/Machine_Learning-Scikit_Learn-orange.svg">
</p>

## 🌟 Overview

The **Order Return Predictor** is a fully functional, intelligent ERP simulation platform designed to bridge the gap between traditional retail databases and modern predictive machine learning workflows. 

Every year, e-commerce giants lose billions in revenue strictly due to logistics delays, sizing friction, and arbitrary customer return behaviors—often entirely passively. This engine takes an active approach: rather than reviewing returns *after* they happen, the predictive pipeline intercepts the order logic organically and enforces active **Decision Engine Action Policies** based on the generated mathematical risk factors.

## 🚀 Why Is This Needed?

In modern logistics, "Risk" is dynamic. A 40% discount on clothing purchased via Cash on Delivery securely in a remote city 1000km away triggers a completely distinct risk vector compared to an electronic appliance purchased in the warehouse's local city on a reliable credit card.

Conventional ERPs handle everything equally. Our system models nuanced interactions to:
1. **Reduce Overhead:** Pre-emptively detect friction points logically and buffer expected delivery estimates instantly.
2. **Flag Discrepancies:** Halt suspicious COD configurations automatically.
3. **Enhance UI Visibility:** Break down complex ML metrics natively into elegant, actionable business dashboards indicating clear instructions (e.g., "Add Size Insert", "Hold for Manager Review").

## 🧠 Core Architecture

The repository merges a simulated business intelligence pipeline consisting of:

- **Database Backbone (`oracledb` + Oracle DB):** High-efficiency structured joins that power live KPI telemetry, dynamic filtering constraints (`HAVING`, `GROUP BY`), and normalized mappings of independent business entities (Customers, Orders, Logistics, Products, Returns).
- **ML Decision Engine (`scikit-learn`):** A sophisticated ensemble pipeline featuring dummy-encoded handling, probability metric extraction via `CalibratedClassifierCV`, and robust anomaly balancing using `SMOTE`.
- **Flask REST API Wrapper:** Orchestrates direct routing between the HTML Javascript frontends, the trained `.pkl` inference model hashes, and the SQL persistence layer.
- **Dynamic Analytic Frontend (Vanilla JS + Chart.js):** Transforms probability statistics mathematically into beautifully color-coded risk heat maps, historical scatter-traces, and fluid tooltips without sluggish reloads.

## 🔍 Key Features

### 1. Simulated Order Forecasting
A dedicated **Simulation UI** lets a logistics manager feed prospective variables into the trained machine structure. The system parses distance dependencies (`pgeocode`), flags geographical offsets, validates the pricing discounts, and automatically drops a granular metric report with distinct risk explanations mapping directly back to native UI inputs.

### 2. Live Agent Actions
When a theoretical return risk exceeds explicit thresholds or hits specific reason combinations—such as *Delivery Delaying* natively combined with large distances—the ERP outputs a direct action instruction rule to the operator, e.g.:
- *"Add a 2-day delivery buffer to ETA."*
- *"Schedule a quick QC defect check for this Electronics item before dispatch."*

### 3. Customer Telemetry Profiling
Profiles track a customer dynamically across their entire lifetime. Using complex backend SQL pipelines instead of stale cached fields, the UI populates real-time telemetry: True Return Rates iteratively computed through volume checks, precise Risk Tier badges (`Low`, `Medium`, `High`), and live accuracy matrices logging how well historical simulated predictions matched actual shipping outcomes.

### 4. Interactive Live Dashboards
Generates full business-wide insights on courier failure rates, delayed fulfillment statistics, pure Return Overview pie constraints, and mapped Category returns natively tracking every anomaly recorded across the warehouse!

## ⚙️ How to Deploy Locally

1. **Verify Services:** Ensure your Oracle Database instance (`OracleServiceXE` or `FREEPDB1`) is actively broadcasting.
2. **Repository Configuration:** Git clone into your isolated workspace. 
```bash
git clone https://github.com/Ashwin-VR/Order-Return-Rate-Dataset.git
```
3. **Dependencies:** Make sure your python environment has all required libraries tracking correctly (e.g., `flask`, `scikit-learn`, `oracledb`, `imblearn`, `pgeocode`, `bcrypt`).
4. **Boot Sequence:** Execute the Flask logic application to spool the internal HTTP sockets:
```bash
cd ERP_Website
python app.py
```
5. **Connect:** Access the ERP portal directly at `http://127.0.0.1:5000` via your standard browser context.

*(Note: Ensure your DB contains the initialized normalized structures. The `sql_data_importer.py` can be utilized natively to bootstrap fresh datasets into the schema directly from the `.csv` root sources if building totally from scratch)*

## 🛠 Project Status

Actively deployed for operational data integration mappings!
