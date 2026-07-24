# Airbnb Investment Intelligence

A Streamlit app that helps property investors evaluate UK Airbnb markets — London, Manchester, Edinburgh, and Bristol — by local authority district (LAD), combining Inside Airbnb data with an AI-generated investment rationale for each area.

## Overview

The app reads a pre-scored, pre-aggregated dataset (produced upstream in Databricks from Inside Airbnb listings, joined to official ONS local authority district boundaries) and a set of AI-generated recommendation/summary/sentiment texts (produced via the OpenAI Batch API and cached as JSON), both hosted on S3. The Streamlit app itself does no scoring or AI generation at runtime — it reads, filters, and displays.

## Features

- **City & investor-profile selection** — London, Manchester, Edinburgh, Bristol; Balanced / Revenue focused / Risk focused investor profiles
- **Filters** — nightly price range, room type, minimum listings per LAD, minimum availability
- **Market overview** — key metrics, a ranked table of local authority districts by investment score, and a choropleth map of LAD boundaries colored by score (scaled to the current selection's min/max for visible contrast)
- **Property types** — price distribution and bedroom-revenue charts, plus investment-scored cards per property type (Entire home/apt, Private room, Shared room)
- **Recommendations** — top-scoring local authority districts and property types for the selected profile, each with an AI-generated investment rationale, and an exportable text memo
- **Review analysis** — AI-generated review summary and positive/negative sentiment theme breakdown for the top-ranked LAD under the current filters
- **Risks & assumptions** — a summary of the model's known limitations (e.g. the London 90-night short-let cap, occupancy as a proxy rather than confirmed bookings, anonymised listing coordinates)
- **Debug panel** (sidebar checkbox) — per-lookup cache hit/miss status with real failure detail for troubleshooting AI cache issues, plus a manual cache-clear control

## Data sources

All data is read directly from a public S3 bucket over HTTPS (no credentials
required by the app):

| Source | Description |
|---|---|
| `listings_city_lad_property_type_aggregated.csv` | Inside Airbnb listings, geospatially joined to ONS local authority districts, aggregated at `(city, local_authority_district, property_type)` grain. Carries pre-computed `lad_score` and `property_type_score` columns (percentile-rank investment score, computed upstream in Databricks — not recalculated by the app). |
| `{city}_lad_boundaries.geojson` | LAD boundary polygons per city, used for the choropleth map. |
| `parsed_cache/{feature}/{key}.json` | AI-generated content — `borough_recommendation`, `property_type_recommendation`, `review_summary`, `sentiment_analysis` — produced via a Databricks + OpenAI Batch API pipeline and cached as static JSON. |

Underlying raw data is from [Inside Airbnb](http://insideairbnb.com/).

## Setup

**Requirements:** Python 3.14+

```bash
git clone https://github.com/adck872/Airbnb-app/
cd Airbnb-app
pip install -r streamlit/requirements.txt
```

## Running locally

```bash
streamlit run streamlit/main.py
```

The app opens at `http://localhost:8501`. No API keys or environment variables are required — all data sources are read from public S3 URLs configured as constants at the top of `main.py` (`LAD_PTYPE_URL`, `LAD_GEOJSON_URLS`) and `cache_loader.py` (`CACHE_BASE_URL`).

If a data source isn't reachable, the app degrades gracefully with an in-app message rather than crashing — check the sidebar debug panel for the specific cause.

## Deployment

https://airbnb-intel.streamlit.app/

## Team

- Fatima Ahmed
- Freya Clifford
- Ireoluwa Badaki
- Lucas Shea
- Yashodhan Kshirsagar
- Shay Balsekar

## Known limitations

See the in-app **Risks & assumptions** tab for the full list
