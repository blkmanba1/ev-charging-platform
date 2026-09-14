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
| *(none yet — SP1 to start)* | | | | | | |

---

## Candidate datasets — China-specific

> **Scope decision:** the supervisor's original email suggested ACN-Data (Caltech), Boulder
> Colorado, and UK National Grid. Those are **out of scope** — we are using Chinese data instead.
> Worth flagging this choice to him at the next meeting so he knows why the recommended sources
> were not used.

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
