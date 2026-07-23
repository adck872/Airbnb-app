import json
import urllib.request

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cache_loader import (
    get_borough_recommendation,
    get_property_type_recommendation,
    get_review_summary,
    get_sentiment,
    get_last_lookups,
)

# Page config
st.set_page_config(
    page_title="Airbnb Intel",
    page_icon="🏠",
    layout="wide",
)

ACCENT = "#D85A30"
GREY = "#B4B2A9"

# Sidebar
with st.sidebar:
    st.markdown("### 🏠 Airbnb Intel")
    st.divider()

    city = st.selectbox("City", ["London", "Manchester", "Edinburgh", "Bristol"])
    investor_profile = st.selectbox("Investor profile", ["Balanced investor", "Revenue focused", "Risk focused"])
    room_type = st.selectbox("Room type", ["All types", "Entire home/apt", "Private room", "Shared room"])

    price_max = st.slider("Nightly price range (up to £)", 20, 500, 300, step=10)
    min_listings = st.slider("Min. listings sampled (per local authority district)", 0, 200, 20, step=10)
    min_availability = st.slider("Min. availability (days/yr)", 0, 365, 60, step=10)

    # debug_mode = st.checkbox("🔧 Show cache lookup debug info", value=False)
    debug_mode = False  # default to off for public deployment

# Data source — LAD level (post geospatial-join). This single table drives the
# investment score, the top-LAD recommendations, the map, the citywide charts,
# the property-type cards, and every AI cache lookup — it's the same grouping
# the AI batch prompts were generated against.
LAD_PTYPE_URL = "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/city_lad_property_type_summary.csv"
LAD_GEOJSON_URLS = {
    "London": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/lad_geojson/london_lad_boundaries.geojson",
    "Manchester": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/lad_geojson/manchester_lad_boundaries.geojson",
    "Edinburgh": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/lad_geojson/edinburgh_lad_boundaries.geojson",
    "Bristol": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/lad_geojson/bristol_lad_boundaries.geojson",
}
LAD_GEOJSON_FEATURE_KEY = "properties.local_authority_district"

#City centre for map framing (not from the geojson)
CITY_CENTER = {
    "London": dict(lat=51.4893, lon=-0.0882, zoom=8.6),
    "Manchester": dict(lat=53.5065, lon=-2.3201, zoom=9.2),
    "Edinburgh": dict(lat=55.9155, lon=-3.2636, zoom=9.6),
    "Bristol": dict(lat=51.4709, lon=-2.6161, zoom=10.6),
}

VALID_CITIES = list(CITY_CENTER.keys())

#Fetch data from an S3 geojson URL and cache the result
@st.cache_data
def load_geojson_from_url(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


@st.cache_data(show_spinner=False)
def _read_csv_cached(url: str) -> pd.DataFrame:
    """Only called on a successful read — a raised exception is never cached
    by st.cache_data, so a fetch failure always retries on the next call."""
    return pd.read_csv(url)


def try_load_csv(url: str) -> tuple[pd.DataFrame | None, str | None]:
    """Returns (df, None) on success or (None, error_message) on failure. Not
    decorated with st.cache_data itself, so a failure is never memoized."""
    try:
        return _read_csv_cached(url), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


#Load the LAD-level listing table. Returns (None, error_message) if not
#reachable — callers must handle that.
def load_lad_data():
    return try_load_csv(LAD_PTYPE_URL)


#Renames the property types to match the UI labels
def _bucket_property_type(pt: str) -> str:
    pt = str(pt)
    if "Entire" in pt:
        return "Entire home/apt"
    if "Private room" in pt:
        return "Private room"
    if "Shared room" in pt:
        return "Shared room"
    return "Other"


def _weighted(d: pd.DataFrame, col: str) -> float:
    return (d[col] * d["listing_count"]).sum() / d["listing_count"].sum()


#Static lookup values for tables and graphs
PRICE_BANDS = [0, 40, 60, 80, 100, 120, 160, 200, 300, float("inf")]
PRICE_LABELS = ["<£40", "£40-60", "£60-80", "£80-100", "£100-120", "£120-160", "£160-200", "£200-300", "£300+"]
ACCOM_BANDS = [0, 1.5, 2.5, 3.5, 4.5, float("inf")]
ACCOM_LABELS = ["Studio", "1 bed", "2 bed", "3 bed", "4 bed+"]
PROPERTY_TYPE_ICONS = {"Entire home/apt": "🏠", "Private room": "🚪", "Shared room": "👥"}


def _empty_lad_tables():
    boroughs = pd.DataFrame(columns=["Borough", "Med. price (£)", "Availability (days/yr)", "Est. revenue (£k)", "Score"])
    return boroughs, [], pd.DataFrame(columns=["Borough", "Score"])


#Score + top-LAD recommendations, computed from the LAD property-type table.
def compute_lad_tables(lad_ptype_raw, city, price_max, min_availability, room_type, min_listings, investor_profile):
    if lad_ptype_raw is None:
        return _empty_lad_tables()

    d = lad_ptype_raw[
        (lad_ptype_raw["city"] == city)
        & (lad_ptype_raw["average_price"] <= price_max)
        & (lad_ptype_raw["availability"] >= min_availability)
    ]
    if room_type != "All types":
        d = d[d["bucket"] == room_type]

    if d.empty:
        return _empty_lad_tables()

    lad_agg = (
        d.groupby("local_authority_district")
        .apply(
            lambda g: pd.Series(
                {
                    "listing_count": g["listing_count"].sum(),
                    "average_price": _weighted(g, "average_price"),
                    "availability": _weighted(g, "availability"),
                    "estimated_revenue": _weighted(g, "estimated_revenue"),
                    "average_review_score": _weighted(g, "average_review_score"),
                    "average_location_score": _weighted(g, "average_location_score"),
                    "reviews_per_month": _weighted(g, "reviews_per_month"),
                    "accommodates": _weighted(g, "accommodates"),
                    # lad_score is constant across every property-type row for a
                    # given LAD (denormalised upstream), so any row's value is
                    # the correct one — .iloc[0] rather than an average of it.
                    "Score": g["lad_score"].iloc[0],
                }
            )
        )
        .reset_index()
    )
    lad_agg = lad_agg[lad_agg["listing_count"] >= min_listings]
    if lad_agg.empty:
        return _empty_lad_tables()

    boroughs_full = lad_agg.sort_values("Score", ascending=False).rename(columns={"local_authority_district": "Borough"})
    boroughs = (
        boroughs_full.head(7)
        .assign(
            **{
                "Med. price (£)": lambda x: x["average_price"].round(0),
                "Availability (days/yr)": lambda x: x["availability"].round(0),
                "Est. revenue (£k)": lambda x: (x["estimated_revenue"] / 1000).round(1),
                "Score": lambda x: x["Score"].round().astype(int),
            }
        )[["Borough", "Med. price (£)", "Availability (days/yr)", "Est. revenue (£k)", "Score"]]
        .reset_index(drop=True)
    )

    borough_recs = []
    for i, row in boroughs.head(3).reset_index(drop=True).iterrows():
        src = lad_agg.loc[lad_agg["local_authority_district"] == row["Borough"]].iloc[0]
        body = (
            f"Median nightly rate of £{row['Med. price (£)']:.0f} with an average availability of "
            f"{row['Availability (days/yr)']:.0f}. Estimated annual revenue of £{row['Est. revenue (£k)']:.1f}k across "
            f"{int(src['listing_count'])} matching listings. Average review score {src['average_review_score']:.2f}/5 "
            f"and location score {src['average_location_score']:.2f}/5."
        )
        ai = get_borough_recommendation(city, row["Borough"], investor_profile)
        if ai is None:
            ai = "AI rationale not yet available for this local authority district — showing the metrics summary above instead."
        borough_recs.append(dict(rank=i + 1, name=row["Borough"], score=int(row["Score"]), body=body, ai=ai))

    return boroughs, borough_recs, boroughs_full[["Borough", "Score"]]


def _empty_citywide_tables():
    price_dist = pd.DataFrame({"Band": PRICE_LABELS, "Listings": [0] * len(PRICE_LABELS)})
    bedroom_revenue = pd.DataFrame({"Bedrooms": ACCOM_LABELS, "Revenue (£)": [0] * len(ACCOM_LABELS)})
    return price_dist, bedroom_revenue, [], [], 0


#Charts + property-type cards, aggregated city-wide across all of that city's LADs
#from the single LAD-level property-type table.
def compute_citywide_tables(lad_ptype_raw, city, price_max, min_availability, room_type, investor_profile):
    ptype = lad_ptype_raw[
        (lad_ptype_raw["city"] == city)
        & (lad_ptype_raw["average_price"] <= price_max)
        & (lad_ptype_raw["availability"] >= min_availability)
    ]
    if room_type != "All types":
        ptype = ptype[ptype["bucket"] == room_type]

    if ptype.empty:
        return _empty_citywide_tables()

    price_binned = ptype.assign(Band=pd.cut(ptype["average_price"], PRICE_BANDS, labels=PRICE_LABELS))
    price_dist = (
        price_binned.groupby("Band", observed=True)["listing_count"]
        .sum()
        .reindex(PRICE_LABELS, fill_value=0)
        .reset_index()
        .rename(columns={"listing_count": "Listings"})
    )

    accom_binned = ptype.assign(Bedrooms=pd.cut(ptype["accommodates"], ACCOM_BANDS, labels=ACCOM_LABELS))
    bedroom_revenue = (
        accom_binned.groupby("Bedrooms", observed=True)
        .apply(lambda d: (d["estimated_revenue"] * d["listing_count"]).sum() / d["listing_count"].sum())
        .reindex(ACCOM_LABELS)
        .reset_index(name="Revenue (£)")
    )
    bedroom_revenue["Revenue (£)"] = bedroom_revenue["Revenue (£)"].round(0)

    ptype = ptype.copy()
    total_listings = ptype["listing_count"].sum()

    property_types = []
    for bucket_name in ["Entire home/apt", "Private room", "Shared room"]:
        d = ptype[ptype["bucket"] == bucket_name]
        if d.empty:
            continue
        count = d["listing_count"].sum()
        price = _weighted(d, "average_price")
        occ = _weighted(d, "availability")
        revenue = _weighted(d, "estimated_revenue")
        rating = _weighted(d, "average_review_score")
        # property_type_score is precomputed upstream (property_type_scored) at
        # (city, property_type) grain, where property_type is Inside Airbnb's raw
        # value (e.g. "Entire rental unit"). Multiple raw types roll into one
        # bucket here for display, so the card's score is a listing-weighted
        # average across whichever raw types are in this bucket.
        score = _weighted(d, "property_type_score")
        property_types.append(
            dict(
                name=bucket_name,
                icon=PROPERTY_TYPE_ICONS[bucket_name],
                share=f"{count / total_listings * 100:.0f}% of listings",
                price=round(price),
                occ=round(occ),
                revenue=round(revenue / 1000, 1),
                rating=round(rating, 2),
                score=round(score),
            )
        )

    property_recs = []
    for prop in sorted(property_types, key=lambda p: p["score"], reverse=True)[:2]:
        body = (
            f"{prop['share']}. Median price £{prop['price']}/night with an average availability score of "
            f"{prop['occ']}. Est. annual revenue £{prop['revenue']}k/yr. Avg. review score (Q) "
            f"{prop['rating']}/5."
        )
        ai = get_property_type_recommendation(prop["name"], investor_profile)
        property_recs.append(dict(name=prop["name"], icon=prop["icon"], score=prop["score"], body=body, ai=ai))

    total_listings = int(ptype["listing_count"].sum())
    return price_dist, bedroom_revenue, property_types, property_recs, total_listings


lad_ptype_df, LAD_LOAD_ERROR = load_lad_data()
LAD_DATA_AVAILABLE = lad_ptype_df is not None
if LAD_DATA_AVAILABLE:
    lad_ptype_df["bucket"] = lad_ptype_df["property_type"].apply(_bucket_property_type)

BOROUGHS, BOROUGH_RECS, CITY_SCORES = compute_lad_tables(
    lad_ptype_df, city, price_max, min_availability, room_type, min_listings, investor_profile
)
if LAD_DATA_AVAILABLE:
    PRICE_DIST, BEDROOM_REVENUE, PROPERTY_TYPES, PROPERTY_RECS, TOTAL_LISTINGS = compute_citywide_tables(
        lad_ptype_df, city, price_max, min_availability, room_type, investor_profile
    )
else:
    PRICE_DIST, BEDROOM_REVENUE, PROPERTY_TYPES, PROPERTY_RECS, TOTAL_LISTINGS = _empty_citywide_tables()

RISKS = [
    ("🔴", "90-night cap (London)",
     "Under the Deregulation Act 2015, London hosts may rent entire properties short-term for a "
     "maximum of 90 nights per calendar year without planning permission. Revenue estimates are "
     "capped accordingly.", "Regulatory", "high"),
    ("🟠", "Occupancy proxy, not actual data",
     "Inside Airbnb estimates occupancy using the San Francisco Model. Calendar \"unavailable\" "
     "nights do not distinguish booked nights from host-blocked nights. True occupancy may differ "
     "significantly.", "Data quality", "med"),
    ("🟠", "Anonymised listing locations",
     "Listing coordinates are offset by up to 150 metres for privacy. LAD-level analysis "
     "is reliable; street-level micro-location analysis requires direct verification.",
     "Data quality", "med"),
    ("🟢", "No purchase price or yield data",
     "Long-term rental comparisons use UK HPI / HM Land Registry data. Purchase prices and gross "
     "yields are approximations. Transaction costs, mortgage costs, and management fees are "
     "excluded.", "Financial", "low"),
    ("🟢", "Snapshot data — no seasonality",
     "Inside Airbnb data is a point-in-time snapshot. Revenue estimates do not reflect seasonal "
     "variation. Actual revenue may be significantly higher in summer and lower in winter.",
     "Operational", "low"),
    ("🟢", "Investment score assumptions",
     "The investment score is precomputed upstream from the raw listings data as a weighted blend "
     "of percentile ranks: 25% estimated revenue, 25% occupancy proxy, 20% reviews per month, 20% "
     "review location score, 10% overall review score. It does not change with the investor profile "
     "selector — profile only affects the tone of the AI-generated text, not the ranking.", "Model", "low"),
]

RISK_BADGE_COLOR = {"high": "#A32D2D", "med": "#854F0B", "low": "#3B6D11"}
RISK_BADGE_BG = {"high": "#FCEBEB", "med": "#FAEEDA", "low": "#EAF3DE"}


def score_color(score: int) -> str:
    if score >= 75:
        return "#3B6D11", "#EAF3DE"  # text, bg  (high)
    if score >= 50:
        return "#854F0B", "#FAEEDA"  # med
    return "#A32D2D", "#FCEBEB"      # low


with st.sidebar:
    if debug_mode:
        st.divider()
        st.markdown("**Cache lookups (most recent)**")
        if st.button("♻️ Clear cache & retry"):
            st.cache_data.clear()
            st.rerun()
        lookups = get_last_lookups()
        if not lookups:
            st.caption("No cache lookups yet this run.")
        else:
            st.dataframe(
                pd.DataFrame(lookups)[["feature", "key", "status"]],
                hide_index=True, width='stretch', height=180,
            )
            failures = [l for l in lookups if l["status"] != "hit"]
            if failures:
                st.markdown("**Failure detail**")
                for f in failures[-10:]:
                    st.code(f"[{f['status']}] {f['feature']}/{f['key']}\n{f['detail']}", language=None)
        if not LAD_DATA_AVAILABLE:
            st.warning("LAD-level CSV not reachable — check LAD_PTYPE_URL in main.py.")


# Tabs
tab_overview, tab_properties, tab_recs, tab_reviews, tab_risks = st.tabs(
    ["🗺️ Market overview", "🏢 Property types", "⭐ Recommendations", "💬 Review analysis", "🛡️ Risks & assumptions"]
)


#Tab 1 — market overview
with tab_overview:
    if not LAD_DATA_AVAILABLE:
        st.info(
            "LAD-level scoring data hasn't been uploaded to S3 yet. See lad_rebuild_spec.md for the "
            "expected file locations — this tab will populate automatically once they're in place."
        )
    elif BOROUGHS.empty:
        st.info("No listings match the current filters — try relaxing the price, availability, or min. listings sliders.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Matching listings", f"{TOTAL_LISTINGS:,}")
        c2.metric("Median nightly price", f"£{BOROUGHS['Med. price (£)'].median():.0f}")
        c3.metric("Avg. availability (days/yr)", f"{BOROUGHS['Availability (days/yr)'].mean():.0f}".replace('%', ''))
        c4.metric("Est. annual revenue (median)", f"£{BOROUGHS['Est. revenue (£k)'].median():.1f}k")

        st.markdown("**Top local authority districts by investment score**")

        def fmt_score(s):
            txt_color, bg_color = score_color(s)
            return f"background-color:{bg_color}; color:{txt_color}; font-weight:600; text-align:center;"

        styled = BOROUGHS.style.map(fmt_score, subset=["Score"]).format(
            {"Med. price (£)": "£{:.0f}", "Availability (days/yr)": "{:.0f}",
             "Est. revenue (£k)": "£{:.1f}k", "Score": "{:.0f}"}
        )
        st.dataframe(styled, hide_index=True, width='stretch')

        st.markdown("**LAD investment score map**")
        st.caption(f"Choropleth of {city}'s local authority districts, coloured by investment score under the current filters. Colour scale is relative to the current selection's min/max, not a fixed 0–100 range.")
        geojson = load_geojson_from_url(LAD_GEOJSON_URLS[city]) if city in LAD_GEOJSON_URLS else None
        if geojson is None:
            st.warning(f"No LAD boundary file configured for {city} yet.")
        elif CITY_SCORES.empty:
            st.info("No listings match the current filters.")
        else:
            score_min = CITY_SCORES["Score"].min()
            score_max = CITY_SCORES["Score"].max()
            if score_min == score_max:
                # Single LAD, or every visible LAD tied on score — a flat
                # range would otherwise render as one undifferentiated colour.
                score_min -= 5
                score_max += 5
            map_fig = go.Figure(
                go.Choroplethmapbox(
                    geojson=geojson,
                    locations=CITY_SCORES["Borough"],
                    z=CITY_SCORES["Score"],
                    featureidkey=LAD_GEOJSON_FEATURE_KEY,
                    colorscale=[[0, "#FCEBEB"], [0.5, "#FAEEDA"], [1, ACCENT]],
                    zmin=score_min,
                    zmax=score_max,
                    marker_opacity=0.85,
                    marker_line_width=0.5,
                    marker_line_color="white",
                    colorbar_title="Score",
                )
            )
            center = CITY_CENTER[city]
            map_fig.update_layout(
                mapbox_style="carto-positron",
                mapbox_zoom=center["zoom"],
                mapbox_center=dict(lat=center["lat"], lon=center["lon"]),
                height=340,
                margin=dict(l=0, r=0, t=0, b=0),
            )
            st.plotly_chart(map_fig, width='stretch')

# Tab 2 — property types
with tab_properties:

    if not LAD_DATA_AVAILABLE:
        st.info(
            "LAD-level data hasn't been uploaded to S3 yet. See lad_rebuild_spec.md for the "
            "expected file location — this tab will populate automatically once it's in place."
        )
    elif not PROPERTY_TYPES:
        st.info("No listings match the current filters.")
    else:
        cols = st.columns(3)
        for col, prop in zip(cols, PROPERTY_TYPES):
            with col:
                with st.container(border=True):
                    st.markdown(f"#### {prop['icon']} {prop['name']}")
                    st.caption(prop["share"])
                    st.write(f"**Median price:** £{prop['price']}/night")
                    st.write(f"**Avg. availability:** {prop['occ']} days/yr")
                    st.write(f"**Est. annual revenue:** £{prop['revenue']}k")
                    st.write(f"**Avg. review score (Q):** {prop['rating']} / 5")
                    st.write(f"**Investment score:** {prop['score']} / 100")
                    st.progress(prop["score"] / 100)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Nightly price distribution**")
            fig1 = go.Figure(go.Bar(x=PRICE_DIST["Band"], y=PRICE_DIST["Listings"], marker_color=ACCENT))
            fig1.update_layout(
                height=260,
                margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig1, width='stretch')

        with col_right:
            st.markdown("**Revenue by bedroom count (entire homes)**")
            bedroom_colors = [GREY, "#888780", ACCENT, "#993C1D", "#4A1B0C"]
            fig3 = go.Figure(
                go.Bar(x=BEDROOM_REVENUE["Bedrooms"], y=BEDROOM_REVENUE["Revenue (£)"], marker_color=bedroom_colors)
            )
            fig3.update_layout(
                height=220, margin=dict(l=10, r=10, t=10, b=10),
                yaxis_tickprefix="£", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig3, width='stretch')


#Tab 3 - recommendations

with tab_recs:
    head_col, btn_col = st.columns([3, 1])
    with head_col:
        st.write(f"Recommendations for: **{investor_profile} · {city} · {room_type}**")
    with btn_col:
        regenerate = st.button("✨ Regenerate", width='stretch')
    #if regenerate:
        #this calls an LLM to refresh the memo with live data

    if not LAD_DATA_AVAILABLE:
        st.info(
            "LAD-level data hasn't been uploaded to S3 yet, so recommendations can't be computed. "
            "See lad_rebuild_spec.md for the expected file location."
        )
    elif not BOROUGH_RECS:
        st.info("No listings match the current filters.")
    else:
        n_boroughs = len(BOROUGH_RECS)
        heading = "Top recommended local authority district" if n_boroughs == 1 else f"Top {n_boroughs} recommended local authority districts"
        st.markdown(f"##### {heading}")
        for rec in BOROUGH_RECS:
            with st.container(border=True):
                top_l, top_r = st.columns([4, 1])
                top_l.markdown(f"**{rec['rank']}. {rec['name']}**")
                top_r.markdown(f"`Score: {rec['score']}`")
                st.write(rec["body"])
                with st.expander("🤖 AI rationale"):
                    st.write(rec["ai"])

    if LAD_DATA_AVAILABLE and PROPERTY_RECS:
        st.markdown("##### Top recommended property types")
        cols = st.columns(2)
        for col, prop in zip(cols, PROPERTY_RECS):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{prop['icon']} {prop['name']}**  `Score: {prop['score']}`")
                    st.write(prop["body"])
                    if prop.get("ai"):
                        with st.expander("🤖 AI rationale"):
                            st.write(prop["ai"])

    if BOROUGH_RECS:
        st.download_button(
            "⬇️ Export memo (.txt)",
            data="\n\n".join(f"{r['rank']}. {r['name']} (Score {r['score']})\n{r['body']}" for r in BOROUGH_RECS),
            file_name="investor_memo.txt",
        )

#Tab 4 - review analysis
with tab_reviews:
    if not LAD_DATA_AVAILABLE:
        st.info("LAD-level scoring data hasn't been uploaded to S3 yet, so there's no top LAD to analyse reviews for.")
    elif BOROUGHS.empty:
        st.info("No listings match the current filters — try relaxing the price, availability, or min. listings sliders.")
    else:
        top_borough = BOROUGHS.iloc[0]["Borough"]
        summary = get_review_summary(city, top_borough)
        sentiment = get_sentiment(city, top_borough)

        head_col, btn_col = st.columns([3, 1])
        with head_col:
            st.write(f"Analysing: **{top_borough}, {city}**")
        #with btn_col:
           # if st.button("✨ Analyse reviews", width='stretch'):
              #  this would call an LLM to summarise fresh review text

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Positive themes**")
            positive_themes = (sentiment or {}).get("positive_themes") or []
            if positive_themes:
                for t in positive_themes:
                    st.write(f"{t['theme']} — {t['pct']}%")
                    st.progress(t["pct"] / 100)
            else:
                st.caption("Sentiment breakdown not available for this LAD yet.")

        with col_right:
            st.markdown("**Negative themes**")
            negative_themes = (sentiment or {}).get("negative_themes") or []
            if negative_themes:
                for t in negative_themes:
                    st.write(f"{t['theme']} — {t['pct']}%")
                    st.progress(t["pct"] / 100)
            else:
                st.caption("Sentiment breakdown not available for this LAD yet.")

        st.markdown("**AI review summary**")
        with st.container(border=True):
            if summary and summary.get("summary"):
                st.markdown(summary["summary"])
                st.caption(summary.get("investment_signal", ""))
            else:
                st.caption(
                    f"No review summary cached yet for {top_borough} — this LAD may have had "
                    "fewer than 5 sampled reviews, or the last batch run hasn't completed."
                )

#Tab 5 - risks and assumptions

with tab_risks:
    st.markdown("##### Risk & assumption summary")
    st.caption(
        "This app is not financial or legal advice. All estimates are based on an Inside Airbnb "
        "snapshot and carry the limitations noted below."
    )

    for icon, title, desc, category, level in RISKS:
        with st.container(border=True):
            r_icon, r_body, r_badge = st.columns([0.4, 4, 1])
            r_icon.markdown(f"### {icon}")
            with r_body:
                st.markdown(f"**{title}**")
                st.caption(desc)
            r_badge.markdown(
                f"<span style='background-color:{RISK_BADGE_BG[level]}; "
                f"color:{RISK_BADGE_COLOR[level]}; padding:2px 8px; border-radius:4px; "
                f"font-size:12px;'>{category}</span>",
                unsafe_allow_html=True,
            )
