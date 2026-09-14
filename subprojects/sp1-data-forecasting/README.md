# SP1 — EV Charging Data Analysis and Demand Forecasting

**Owner:** Xu Yuxuan (徐宇轩)
**Consumes:** raw public datasets
**Produces:** `data/processed/sp1-demand-forecast-v1.csv` → SP2, SP4, SP5

## Tasks (from the official brief)
- Collect and preprocess public EV charging datasets.
- Analyse charging patterns and user behaviour.
- Develop machine learning models to predict future charging demand.
- Evaluate forecasting accuracy and model performance.

## Candidate datasets
ACN-Data (Caltech/JPL) · Boulder, Colorado EV data · UK National Grid data

## Candidate models
Linear Regression · Random Forest · LSTM · XGBoost

## Output contract
See `docs/integration-contract.md` → *SP1 → SP2 · Demand forecast*.

## Layout
```
src/          # reusable code
notebooks/    # exploration, clearly numbered
```
