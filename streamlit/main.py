import pandas as pd
import plotly.graph_objects as go
import streamlit as st


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
    min_listings = st.slider("Min. listings sampled (per neighbourhood)", 0, 200, 20, step=10)
    min_availability = st.slider("Min. availability (days/yr)", 0, 365, 60, step=10)
 
#Data loaded from s3 buckets 
NEIGHBOURHOOD_URL = (
    "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/listings_city_neighbourhood_aggregated/part-00000-tid-8659415770633088101-e2bf734d-3463-4031-8135-a30a45be0b61-128-1-c000.csv"
)
PROPERTY_TYPE_URL = (
    "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/listings_city_neighbourhood_property_type_aggregated/part-00000-tid-4392307639532036816-409e45e1-3443-4936-b33f-f4b72afde7f0-129-1-c000.csv"
)

GEOJSON_URLS = {
    "London": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/london_neighbourhoods.geojson",
    "Manchester": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/manchester_neighbourhoods+.geojson",
    "Edinburgh": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/edinburgh_neighbourhoods+.geojson",
    "Bristol": "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/bristol_neighbourhoods.geojson",
}
#City centre for map framing (not from the geojson)
CITY_CENTER = {
    "London": dict(lat=51.4893, lon=-0.0882, zoom=8.6),
    "Manchester": dict(lat=53.5065, lon=-2.3201, zoom=9.2),
    "Edinburgh": dict(lat=55.9155, lon=-3.2636, zoom=9.6),
    "Bristol": dict(lat=51.4709, lon=-2.6161, zoom=10.6),
}

#Fetch data from the S3 geojson URLs and cache the results 
@st.cache_data
def load_geojson(city: str) -> dict:
    import json
    import urllib.request

    with urllib.request.urlopen(GEOJSON_URLS[city]) as resp:
        return json.load(resp)

@st.cache_data
def load_neighbourhood_city_map() -> dict:
    mapping = {}
    for city in GEOJSON_URLS:
        gj = load_geojson(city)
        for feat in gj["features"]:
            mapping[feat["properties"]["neighbourhood"]] = city
    return mapping



#Match the city column in the dataframes to the cities in the geojson files 
def _ensure_city_column(df: pd.DataFrame) -> pd.DataFrame:
    city_col = next((c for c in df.columns if "city" in c.lower()), None)
    lookup = load_neighbourhood_city_map()
    if city_col is not None:
        df = df.rename(columns={city_col: "city"})
        df["city"] = df["city"].where(df["city"].isin(GEOJSON_URLS.keys()), df["neighbourhood"].map(lookup))
    else:
        df["city"] = df["neighbourhood"].map(lookup)
    return df


#Load and cache the listing tables 
@st.cache_data
def load_data():
    nbhd = pd.read_csv(NEIGHBOURHOOD_URL)
    ptype = pd.read_csv(PROPERTY_TYPE_URL)
    #Make colum names match
    ptype = ptype.rename(columns={"avg_median_property_priceavg_median_price": "avg_median_property_price"})
    nbhd = _ensure_city_column(nbhd)
    ptype = _ensure_city_column(ptype)
    return nbhd, ptype

#Normalise function for score 
def _normalize(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi - lo == 0:
        return pd.Series(50.0, index=s.index)
    return (s - lo) / (hi - lo) * 100

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


# Investor-profile presets for the Score formula: Q=rating, I=revenue, P=popularity/no. of
# bookings, N=location quality, M=guest-capacity (maintenance-cost proxy, subtracted).
INVESTOR_WEIGHTS = {
    "Balanced investor": dict(Q=0.30, I=0.30, P=0.20, N=0.10, M=0.10),
    "Revenue focused": dict(Q=0.15, I=0.50, P=0.20, N=0.05, M=0.10),
    "Risk focused": dict(Q=0.40, I=0.15, P=0.10, N=0.35, M=0.00),
}

#Static lookup values for tables and graphs 
PRICE_BANDS = [0, 40, 60, 80, 100, 120, 160, 200, 300, float("inf")]
PRICE_LABELS = ["<£40", "£40–60", "£60–80", "£80–100", "£100–120", "£120–160", "£160–200", "£200–300", "£300+"]
ACCOM_BANDS = [0, 1.5, 2.5, 3.5, 4.5, float("inf")]
ACCOM_LABELS = ["Studio", "1 bed", "2 bed", "3 bed", "4 bed+"]
PROPERTY_TYPE_ICONS = {"Entire home/apt": "🏠", "Private room": "🚪", "Shared room": "👥"}


def _empty_tables():
    boroughs = pd.DataFrame(columns=["Borough", "Med. price (£)", "Occupancy (%)", "Est. revenue (£k)", "Score"])
    price_dist = pd.DataFrame({"Band": PRICE_LABELS, "Listings": [0] * len(PRICE_LABELS)})
    bedroom_revenue = pd.DataFrame({"Bedrooms": ACCOM_LABELS, "Revenue (£)": [0] * len(ACCOM_LABELS)})
    return boroughs, price_dist, bedroom_revenue, [], [], [], 0, pd.DataFrame(columns=["Borough", "Score"])


#Use filters on side bar to compute the tables and graphs for the app
def compute_tables(ptype_raw, city, price_max, min_availability, room_type, min_listings, investor_profile):
    ptype = ptype_raw[
        (ptype_raw["city"] == city)
        & (ptype_raw["average_price"] <= price_max)
        & (ptype_raw["availability"] >= min_availability)
    ]
    if room_type != "All types":
        ptype = ptype[ptype["bucket"] == room_type]

    if ptype.empty:
        return _empty_tables()

    # Re-aggregate up to neighbourhood level from the filtered rows
    nbhd_agg = (
        ptype.groupby("neighbourhood")
        .apply(
            lambda g: pd.Series(
                {
                    "listing_count": g["listing_count"].sum(),
                    "average_price": _weighted(g, "average_price"),
                    "availability": _weighted(g, "availability"),
                    "estimated_revenue": _weighted(g, "estimated_revenue"),
                    "average_review_score": _weighted(g, "average_review_score"),
                    "average_location_score": _weighted(g, "average_location_score"),
                    "accomodates": _weighted(g, "accomodates"),
                }
            )
        )
        .reset_index()
    )
    nbhd_agg = nbhd_agg[nbhd_agg["listing_count"] >= min_listings]
    if nbhd_agg.empty:
        return _empty_tables()

    w = INVESTOR_WEIGHTS[investor_profile]
    nbhd_agg["Score"] = (
        w["Q"] * _normalize(nbhd_agg["average_review_score"])
        + w["I"] * _normalize(nbhd_agg["estimated_revenue"])
        + w["P"] * _normalize(nbhd_agg["listing_count"])
        + w["N"] * _normalize(nbhd_agg["average_location_score"])
        - w["M"] * _normalize(nbhd_agg["accomodates"])
    )
    nbhd_agg["Score"] = _normalize(nbhd_agg["Score"]).round().astype(int)

    #Sort boroughs by score 
    boroughs_full = nbhd_agg.sort_values("Score", ascending=False).rename(columns={"neighbourhood": "Borough"})
    boroughs = (
        boroughs_full.head(7)
        .assign(
            **{
                "Med. price (£)": lambda d: d["average_price"].round(0),
                "Occupancy (%)": lambda d: d["availability"].round(0),
                "Est. revenue (£k)": lambda d: (d["estimated_revenue"] / 1000).round(1),
            }
        )[["Borough", "Med. price (£)", "Occupancy (%)", "Est. revenue (£k)", "Score"]]
        .reset_index(drop=True)
    )

    price_binned = ptype.assign(Band=pd.cut(ptype["average_price"], PRICE_BANDS, labels=PRICE_LABELS))
    price_dist = (
        price_binned.groupby("Band", observed=True)["listing_count"]
        .sum()
        .reindex(PRICE_LABELS, fill_value=0)
        .reset_index()
        .rename(columns={"listing_count": "Listings"})
    )

    accom_binned = ptype.assign(Bedrooms=pd.cut(ptype["accomodates"], ACCOM_BANDS, labels=ACCOM_LABELS))
    bedroom_revenue = (
        accom_binned.groupby("Bedrooms", observed=True)
        .apply(lambda d: (d["estimated_revenue"] * d["listing_count"]).sum() / d["listing_count"].sum())
        .reindex(ACCOM_LABELS)
        .reset_index(name="Revenue (£)")
    )
    bedroom_revenue["Revenue (£)"] = bedroom_revenue["Revenue (£)"].round(0)

    ptype = ptype.copy()
    total_listings = ptype["listing_count"].sum()
    ptype["_norm_review"] = _normalize(ptype["average_review_score"])
    ptype["_norm_revenue"] = _normalize(ptype["estimated_revenue"])
    ptype["_norm_count"] = _normalize(ptype["listing_count"])

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
        score = (
            0.30 * _weighted(d, "_norm_review")
            + 0.30 * _weighted(d, "_norm_revenue")
            + 0.20 * min(occ, 100)
            + 0.20 * _weighted(d, "_norm_count")
        )
        property_types.append(
            dict(
                name=bucket_name,
                icon=PROPERTY_TYPE_ICONS[bucket_name],
                share=f"{count / total_listings * 100:.0f}% of listings",
                price=round(price),
                occ=round(occ),
                revenue=round(revenue / 1000, 1),
                rating=round(rating, 2),
                score=min(round(score), 100),
            )
        )

    borough_recs = []
    for i, row in boroughs.head(3).reset_index(drop=True).iterrows():
        src = nbhd_agg.loc[nbhd_agg["neighbourhood"] == row["Borough"]].iloc[0]
        body = (
            f"Median nightly rate of £{row['Med. price (£)']:.0f} with an average availability score of "
            f"{row['Occupancy (%)']:.0f}. Estimated annual revenue of £{row['Est. revenue (£k)']:.1f}k across "
            f"{int(src['listing_count'])} matching listings. Average review score {src['average_review_score']:.2f}/5 "
            f"and location score {src['average_location_score']:.2f}/5."
        )
        ai = (
         "Will be generated with AI"
        )
        borough_recs.append(dict(rank=i + 1, name=row["Borough"], score=int(row["Score"]), body=body, ai=ai))

    property_recs = []
    for prop in sorted(property_types, key=lambda p: p["score"], reverse=True)[:2]:
        body = (
            f"{prop['share']}. Median price £{prop['price']}/night with an average availability score of "
            f"{prop['occ']}. Est. annual revenue £{prop['revenue']}k/yr. Avg. review score (Q) "
            f"{prop['rating']}/5."
        )
        property_recs.append(dict(name=prop["name"], icon=prop["icon"], score=prop["score"], body=body))

    total_listings = int(ptype["listing_count"].sum())
    return boroughs, price_dist, bedroom_revenue, property_types, borough_recs, property_recs, total_listings, boroughs_full[["Borough", "Score"]]


nbhd_df, ptype_df = load_data()
ptype_df["bucket"] = ptype_df["property_type"].apply(_bucket_property_type)

BOROUGHS, PRICE_DIST, BEDROOM_REVENUE, PROPERTY_TYPES, BOROUGH_RECS, PROPERTY_RECS, TOTAL_LISTINGS, CITY_SCORES = compute_tables(
    ptype_df, city, price_max, min_availability, room_type, min_listings, investor_profile
)

# Place holders for AI sentiment analysis 
POSITIVE_THEMES = [("Location", 84), ("Cleanliness", 76), ("Value", 68), ("Check-in", 61), ("Comfort", 55)]
NEGATIVE_THEMES = [("Noise", 32), ("Wi-Fi", 18), ("Communication", 14), ("Size", 11), ("Access", 8)]

AI_REVIEW_SUMMARY = (
    ""
)

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
     "Listing coordinates are offset by up to 150 metres for privacy. Neighbourhood-level analysis "
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
     "Score variables Q, I, P, N, and M are normalised to 0–100 before weighting. The maintenance "
     "penalty (M) is a proxy for bed/bath count and does not account for actual property condition "
     "or local management costs.", "Model", "low"),
]

RISK_BADGE_COLOR = {"high": "#A32D2D", "med": "#854F0B", "low": "#3B6D11"}
RISK_BADGE_BG = {"high": "#FCEBEB", "med": "#FAEEDA", "low": "#EAF3DE"}


def score_color(score: int) -> str:
    if score >= 75:
        return "#3B6D11", "#EAF3DE"  # text, bg  (high)
    if score >= 50:
        return "#854F0B", "#FAEEDA"  # med
    return "#A32D2D", "#FCEBEB"      # low


# Tabs
tab_overview, tab_properties, tab_recs, tab_reviews, tab_risks = st.tabs(
    ["🗺️ Market overview", "🏢 Property types", "⭐ Recommendations", "💬 Review analysis", "🛡️ Risks & assumptions"]
)


#Tab 1 — market overview
with tab_overview:
    if BOROUGHS.empty:
        st.info("No listings match the current filters — try relaxing the price, availability, or min. listings sliders.")
    else:





        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Matching listings", f"{TOTAL_LISTINGS:,}")
        c2.metric("Median nightly price", f"£{BOROUGHS['Med. price (£)'].median():.0f}")
        c3.metric("Avg. occupancy proxy", f"{BOROUGHS['Occupancy (%)'].mean():.0f}%")
        c4.metric("Est. annual revenue (median)", f"£{BOROUGHS['Est. revenue (£k)'].median():.1f}k")

        st.markdown("**Top boroughs by investment score**")

        def fmt_score(s):
                txt_color, bg_color = score_color(s)
                return f"background-color:{bg_color}; color:{txt_color}; font-weight:600; text-align:center;"

        styled = BOROUGHS.style.map(fmt_score, subset=["Score"]).format(
                {"Med. price (£)": "£{:.0f}", "Occupancy (%)": "{:.0f}%",
                 "Est. revenue (£k)": "£{:.1f}k", "Score": "{:.0f}"}
        )
        st.dataframe(styled, hide_index=True, width='stretch')

        st.markdown("**Neighbourhood investment score map**")
        st.caption(f"Choropleth of {city} neighbourhoods, coloured by investment score under the current filters.")
        if CITY_SCORES.empty:
                st.info("No listings match the current filters.")
        else:
            geojson = load_geojson(city)
            map_fig = go.Figure(
                go.Choroplethmapbox(
                    geojson=geojson,
                    locations=CITY_SCORES["Borough"],
                    z=CITY_SCORES["Score"],
                    featureidkey="properties.neighbourhood",
                    colorscale=[[0, "#FCEBEB"], [0.5, "#FAEEDA"], [1, ACCENT]],
                    zmin=0,
                    zmax=100,
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

    if not PROPERTY_TYPES:
        st.info("No listings match the current filters.")
    else:
        cols = st.columns(3)
        for col, prop in zip(cols, PROPERTY_TYPES):
            with col:
                with st.container(border=True):
                    st.markdown(f"#### {prop['icon']} {prop['name']}")
                    st.caption(prop["share"])
                    st.write(f"**Median price:** £{prop['price']}/night")
                    st.write(f"**Avg. occupancy:** {prop['occ']}%")
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

    if not BOROUGH_RECS:
        st.info("No listings match the current filters.")
    else:
        st.markdown("##### Top 3 recommended boroughs")
        for rec in BOROUGH_RECS:
            with st.container(border=True):
                top_l, top_r = st.columns([4, 1])
                top_l.markdown(f"**{rec['rank']}. {rec['name']}**")
                top_r.markdown(f"`Score: {rec['score']}`")
                st.write(rec["body"])
                with st.expander("🤖 AI rationale"):
                    st.write(rec["ai"])

        st.markdown("##### Top recommended property types")
        cols = st.columns(2)
        for col, prop in zip(cols, PROPERTY_RECS):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{prop['icon']} {prop['name']}**  `Score: {prop['score']}`")
                    st.write(prop["body"])

        st.download_button(
            "⬇️ Export memo (.txt)",
            data="\n\n".join(f"{r['rank']}. {r['name']} (Score {r['score']})\n{r['body']}" for r in BOROUGH_RECS),
            file_name="investor_memo.txt",
        )

#Tab 4 - review analysis
with tab_reviews:
    head_col, btn_col = st.columns([3, 1])
    with head_col:
        st.write("Analysing: **Southwark · 1,240 reviews sampled**")
    #with btn_col:
       # if st.button("✨ Analyse reviews", width='stretch'):
          #  this would call an LLM to summarise fresh review text

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**Positive themes**")
        for theme, pct in POSITIVE_THEMES:
            st.write(f"{theme} — {pct}%")
            st.progress(pct / 100)

    with col_right:
        st.markdown("**Negative themes**")
        for theme, pct in NEGATIVE_THEMES:
            st.write(f"{theme} — {pct}%")
            st.progress(pct / 100)

    #st.markdown("**AI review summary**")
   # with st.container(border=True):
    #    st.markdown(AI_REVIEW_SUMMARY)

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