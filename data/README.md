# Data directory

**Datasets are never committed to this repository.** The sub-folders below are git-ignored;
only this README (and `.gitkeep` placeholders) are tracked.

```
data/
├── raw/        # exactly as downloaded — never edit these files
├── interim/    # partially cleaned, intermediate artefacts
└── processed/  # contract-compliant outputs that other subsystems consume
```

## Rules

1. **`raw/` is read-only.** Never overwrite. If a file is wrong, re-download it.
2. **`processed/` obeys `docs/integration-contract.md`** — 1-hour resolution, UTC, CNY.
3. Every dataset you bring in gets a row in the register below **in the same PR**.
4. **All datasets must be China-specific** (locked at kickoff — the project targets the
   Chinese market, so tariffs, carbon intensity, and charging behaviour must all be Chinese).

## Dataset register

| Dataset | Owner (SP) | Source URL | Licence | Downloaded | Size | Notes |
|---|---|---|---|---|---|---|
| **Electric vehicle charging order data** (Beijing / Shanghai / Guangzhou) | SP1 | [figshare 28263986](https://figshare.com/articles/dataset/Electric_vehicle_charging_order_data/28263986) · DOI [10.6084/m9.figshare.28263986.v1](https://doi.org/10.6084/m9.figshare.28263986.v1) | **MIT** | 2026-09-14 | 13.5 MB archive · 76.9 MB CSV · 1,295,394 rows | Session-level public-station charging orders. Fetch with `python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --dataset cn-charging-orders` — it verifies the SHA-256 before use. Details and caveats below. |

### Dataset notes — figshare 28263986 (SP1, primary dataset)

Verified locally from the downloaded files, not from the abstract:

| Property | Measured value |
|---|---|
| Files | `bjgunrecords.csv`, `shgunrecords.csv`, `gzgunrecords.csv` (one per city) |
| Header | `gunId,stationId,time_start,power,time_end` |
| Rows | Beijing 467,940 · Shanghai 358,849 · Guangzhou 468,605 · **total 1,295,394** |
| Stations / guns | 1,847 stations (749 BJ, 657 SH, 441 GZ) · 18,556 guns |
| Time span | 2024-01-17 00:02 → 2024-02-18 17:38 local (33 days) |
| Timestamps | second resolution, **naive local time** — read as `Asia/Shanghai` |
| `power` | one of ~18 discrete values (0, 3.3, 3.5, 7, 10, 15, 30, 40, 60, 90, 120, 150 …), i.e. the **rated power of the gun in kW** |
| Session length | median 0.74–0.92 h, mean 1.09–1.39 h, max 24 h (padded/idle connections) |
| Missing | no vehicle id, no delivered kWh, no tariff/price, no station coordinates (only a numeric `stationId`) |
| SHA-256 of archive | `54deec46afa5d39a6803ef15d694bcfe598f971f6551a0baf7809a1a039a060c` |

**Four things a reader must know before using this data** — they are also written into every
generated `.meta.json`:

1. **`power` is a rating, not a measurement.** Energy is therefore derived as
   `power × duration`, which is an **upper bound** on delivered energy: it ignores DC fast-charge
   tapering and the time a car stays plugged in after charging has finished. At 1-hour resolution
   the derived series is best described as *connected charging power* (kW ≈ kWh per interval),
   which is the quantity the grid actually feels — but it is not metered energy.
2. **The published abstract does not match the files.** The abstract says 769,225 orders from
   1,702 stations for 1–31 January 2024 and mentions Beijing only implicitly; the files contain
   1,295,394 orders from 1,847 stations spanning 17 January – 18 February 2024. The README inside
   the archive is explicit that all three cities are included. **Cite the measured figures**, and
   say that they were measured rather than quoted.
3. **The abstract's "location of the charging station" claim is not supported** by the columns —
   only a numeric `stationId` is present.
4. **303 sessions have `time_end <= time_start`** and 3 lead with `power = 0`; the adapter pads a
   broken session to one minute so its energy still lands in the hour it started, and zero-power
   sessions contribute 0 kWh. Neither is silently dropped.

### Second-choice datasets (evaluated, not used)

Recorded so the search does not have to be repeated — see
`data/raw/dataset-research.md` (git-ignored) for the full reconnaissance with verification logs.
**These files are research notes, not deliverable data.**

| Candidate | Why it was not chosen |
|---|---|
| **MP-EVData** (figshare 29882366, CC BY 4.0) | Ready-made hourly load for 10 stations, but the city is unnamed and **part of the release is explicitly AI-generated synthetic data** — it would have to be labelled as such throughout the dissertation |
| **UrbanEV / ST-EVCDP** (Shenzhen, CC0 1.0 / MIT) | Hourly zone-level volume and duration for 275 zones — aggregated to zone level, **not session-level**, so no session behaviour and no power column |
| **Autosun Shenzhen** (Mendeley, CC BY 4.0) | 1-minute resolution but grouped by data owner instead of station, and the norms are under-sampled |
| **Science Data Bank / 科学数据银行 (scidb.cn)** | Two relevant Chinese datasets were found by title (CSTR 16666.11.nbsdc.Lv8h80yV, 16666.11.nbsdc.p0his6rt) but both landing pages are JavaScript-only and no licence, schema, or download link could be confirmed |
| **China Charging Alliance / EVCIPA** | Publishes monthly national and provincial aggregates only — no time series, no sessions |
| **Beijing / Shanghai / Shenzhen municipal platforms, State Grid / CSG** | Framed as regulatory monitoring systems; no public session-level or load time-series endpoint found |
| **IEEE DataPort annual load dataset** | Paywalled subscription |


---

## Candidate datasets — China-specific

> **Scope decision (supervisor-approved):** the kickoff email suggested ACN-Data (Caltech),
> Boulder Colorado, and UK National Grid data. Those are **superseded** — we use Chinese data,
> and **Dr Ghias has confirmed this is acceptable**. The original suggestions are recorded here
> only so the rationale stays documented if the question comes up again.

### EV charging demand (SP1)

| Source | What it gives | Access |
|---|---|---|
| **Science Data Bank / 科学数据银行** (scidb.cn) | Chinese EV charging session datasets published with research papers | Open, varies by dataset |
| **China Charging Alliance / 中国充电联盟 (evcipa.org.cn)** | Monthly national and provincial charging pile counts, utilisation and energy statistics | Public reports (aggregate only) |
| **Provincial / municipal charging service platforms** (e.g. Beijing, Shanghai, Shenzhen, Guangdong) | Real charging session records where published | Varies; often aggregate |
| **CNKI / 知网 & Wanfang papers** | Papers publishing derived characteristics of Chinese charging behaviour | Papers only — cite as secondary evidence |
| **State Grid / China Southern Power Grid open data portals** | Load profiles and some charging station data | Registration often required |

**Honest constraint:** China publishes far less *open, session-level* EV charging data than the
US or Europe. The strongest public equivalents to ACN-Data are specific research datasets on
Science Data Bank. Expect to spend real effort here, and be prepared to justify the dataset you
choose in the dissertation. If session-level data proves unavailable, the fallback is to build a
**calibrated synthetic profile** from published Chinese aggregate statistics — defensible, but
it must be documented as synthetic.

### Electricity tariffs (SP2)

| Source | What it gives |
|---|---|
| **National Development and Reform Commission (NDRC) / 国家发改委** | National peak-valley time-of-use pricing policy |
| **Provincial DRC price bureaus** (e.g. 广东省发改委, 江苏省发改委) | Actual provincial ToU tariff schedules — the numbers we need |
| **Provincial grid company announcements** | Published peak/flat/valley windows and rates |

China's **peak-valley ToU tariff** structure (峰谷分时电价) is exactly the mechanism SP2's
scheduler should exploit — this is a well-defined, genuinely Chinese policy instrument and
should be a strength of the project.

### Solar generation (SP3)

| Source | What it gives |
|---|---|
| **China Meteorological Administration / 中国气象局** | Irradiance observations |
| **China Meteorological Data Service Centre** (data.cma.cn) | Historical radiation and sunshine data |
| **ERA5 reanalysis** (Copernicus) | Global, includes China — free and well-documented |
| **NASA POWER** | Free, easy API, covers China at hourly resolution |
| **PVGIS** | Free PV yield modelling, covers China |

ERA5 / NASA POWER are the pragmatic choice: free, hourly, no registration, and defensible in a
dissertation. Note in `raw/` notes that they are reanalysis/modelled rather than measured.

### Grid carbon intensity (SP5)

| Source | What it gives |
|---|---|
| **Ministry of Ecology and Environment / 生态环境部** | Published regional grid emission factors |
| **Provincial grid average carbon emission factors** | gCO₂/kWh by province — what SP5's baseline needs |
| **China Electricity Council / 中电联** | Generation mix and carbon intensity reporting |

Prefer a **published official factor** over a self-computed one — SP5 will need a citable
reference in the dissertation.

### Charging station metadata (SP4)

| Source | What it gives |
|---|---|
| **Open Charge Map** | Station locations, connector types (includes China, patchy) |
| **Provincial platform APIs** | Station status where available |

---

## Quick check before you commit

```bash
git status --short          # nothing under data/raw, data/interim, data/processed should appear
```
