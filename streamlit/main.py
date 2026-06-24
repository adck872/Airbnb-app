"""
Airbnb Investment Intelligence — Streamlit version
Simplified port of the original HTML/Chart.js mock-up.

Run with:
    streamlit run airbnb_investment_intelligence_app.py
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Airbnb Intel",
    page_icon="🏠",
    layout="wide",
)

ACCENT = "#D85A30"
GREY = "#B4B2A9"

# --------------------------------------------------------------------------
# Dummy data (stand-ins for the original Inside Airbnb snapshot)
# --------------------------------------------------------------------------

BOROUGHS = pd.DataFrame(
    [
        ("Southwark", 138, 67, 33.8, 88),
        ("Tower Hamlets", 125, 65, 29.7, 84),
        ("Hackney", 119, 63, 27.4, 81),
        ("Lambeth", 108, 61, 24.1, 74),
        ("Islington", 145, 59, 26.2, 71),
        ("Westminster", 198, 55, 31.5, 68),
        ("Bromley", 82, 44, 13.1, 41),
    ],
    columns=["Borough", "Med. price (£)", "Occupancy (%)", "Est. revenue (£k)", "Score"],
)

PRICE_DIST = pd.DataFrame(
    {
        "Band": ["<£40", "£40–60", "£60–80", "£80–100", "£100–120", "£120–160", "£160–200", "£200–300", "£300+"],
        "Listings": [4200, 9800, 15400, 18200, 16800, 12300, 7100, 4200, 1800],
    }
)

BEDROOM_REVENUE = pd.DataFrame(
    {
        "Bedrooms": ["Studio", "1 bed", "2 bed", "3 bed", "4 bed+"],
        "Revenue (£)": [18000, 27000, 38000, 52000, 74000],
    }
)

STL_VS_LTR = pd.DataFrame(
    {
        "Type": ["Entire home", "Private room"],
        "Short-term (90-night cap)": [2800, 940],
        "Long-term rental": [1950, 850],
    }
)

PROPERTY_TYPES = [
    dict(name="Entire home/apt", icon="🏠", share="54% of listings", price=148, occ=62,
         revenue=33.5, rating=4.62, score=86),
    dict(name="Private room", icon="🚪", share="43% of listings", price=68, occ=55,
         revenue=13.7, rating=4.58, score=61),
    dict(name="Shared room", icon="👥", share="3% of listings", price=38, occ=47,
         revenue=6.5, rating=4.31, score=34),
]

BOROUGH_RECS = [
    dict(rank=1, name="Southwark", score=88,
         body="High demand near London Bridge, Borough Market, and Tate Modern. Median nightly "
              "rate of £138 with 67% occupancy. Entire homes dominate. Lower proportion of "
              "professional hosts signals room to compete.",
         ai="Southwark ranks first because it balances above-median pricing with consistently high "
            "occupancy relative to comparable boroughs. Guest reviews highlight proximity to central "
            "attractions and transport links as key positives. The area shows lower-than-average "
            "90-night saturation risk, meaning demand appears genuine rather than concentrated in "
            "short windows."),
    dict(rank=2, name="Tower Hamlets", score=84,
         body="Strong demand from tech workers and tourists visiting Shoreditch, Spitalfields, and "
              "Canary Wharf. Median £125/night. Entire 2-bed flats perform particularly well. High "
              "review volume improves data confidence.",
         ai="Tower Hamlets combines strong occupancy with a diverse guest mix, reducing seasonal "
            "volatility. Reviews frequently cite walkability and nightlife access. Minor risk: a "
            "subset of listings shows review velocity decline, potentially signalling emerging "
            "supply pressure in certain neighbourhoods."),
    dict(rank=3, name="Hackney", score=81,
         body="Popular with younger travellers and cultural tourists. Median £119/night with 63% "
              "occupancy. Lower property prices vs. inner London may improve gross yield. "
              "Neighbourhood feel positively mentioned in reviews.",
         ai="Hackney's investment case rests on growing supply of attractive entire homes, strong "
            "review sentiment, and relatively lower acquisition cost. Main caveat: slight host "
            "concentration risk — a small number of multi-listing hosts account for a meaningful "
            "share of revenue, complicating like-for-like benchmarking."),
]

PROPERTY_RECS = [
    dict(name="Entire 2-bed flat", icon="🏠", score=91,
         body="Best risk-adjusted return. Accommodates 2–4 guests, attracting couples and small "
              "groups. Median est. revenue £38k/yr. High avg. rating (Q = 4.71). Maintenance "
              "penalty (M) partially offset by strong income (I)."),
    dict(name="Entire 1-bed flat", icon="🏢", score=82,
         body="Lower entry point with strong solo/couple demand. Est. revenue £27k/yr. Lower M "
              "penalty (fewer beds/baths). Good for first-time hosts managing maintenance overhead."),
]

POSITIVE_THEMES = [("Location", 84), ("Cleanliness", 76), ("Value", 68), ("Check-in", 61), ("Comfort", 55)]
NEGATIVE_THEMES = [("Noise", 32), ("Wi-Fi", 18), ("Communication", 14), ("Size", 11), ("Access", 8)]

AI_REVIEW_SUMMARY = (
    "Across the sampled Southwark reviews, guests consistently praise the central location and "
    "ease of access to transport links. Cleanliness is a strong differentiator for top-rated "
    "listings. The most common concern is ambient noise, particularly near Borough Market and the "
    "Jubilee Line. Wi-Fi reliability is flagged in roughly 1 in 5 reviews — a quick operational win "
    "for hosts. Communication scores are strong overall, with rare negative outliers linked to "
    "delayed check-in responses.\n\n"
    "**Investment signal:** Noise complaints are structural (street-level and rail adjacency) rather "
    "than operational — a property on a quieter residential street in the same borough avoids this "
    "cluster of negative sentiment."
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


# --------------------------------------------------------------------------
# Sidebar — filters
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏠 Airbnb Intel")
    st.divider()

    city = st.selectbox("City", ["London", "Manchester", "Edinburgh", "Bristol", "Birmingham"])
    investor_profile = st.selectbox("Investor profile", ["Balanced investor", "Revenue focused", "Risk focused"])
    room_type = st.selectbox("Room type", ["All types", "Entire home/apt", "Private room", "Shared room"])

    price_max = st.slider("Nightly price range (up to £)", 20, 500, 300, step=10)
    min_reviews = st.slider("Min. reviews", 0, 100, 10, step=5)
    min_availability = st.slider("Min. availability (days/yr)", 0, 365, 60, step=10)

    st.divider()
    st.caption("Data: Inside Airbnb snapshot.  \nNot financial or legal advice.")

# --------------------------------------------------------------------------
# Header notice
# --------------------------------------------------------------------------
st.warning(
    "**London short-term letting rule:** Without planning permission, hosts are restricted to "
    "90 nights per calendar year. This affects estimated revenue calculations.",
    icon="⚠️",
)

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
tab_overview, tab_properties, tab_recs, tab_reviews, tab_risks = st.tabs(
    ["🗺️ Market overview", "🏢 Property types", "⭐ Recommendations", "💬 Review analysis", "🛡️ Risks & assumptions"]
)

# ==========================================================================
# TAB 1 — MARKET OVERVIEW
# ==========================================================================
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active listings", "86,341")
    c2.metric("Median nightly price", "£112")
    c3.metric("Avg. occupancy proxy", "58%")
    c4.metric("Est. annual revenue (median)", "£23.8k")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Top boroughs by investment score**")

        def fmt_score(s):
            txt_color, bg_color = score_color(s)
            return f"background-color:{bg_color}; color:{txt_color}; font-weight:600; text-align:center;"

        styled = BOROUGHS.style.map(fmt_score, subset=["Score"]).format(
            {"Med. price (£)": "£{:.0f}", "Occupancy (%)": "{:.0f}%",
             "Est. revenue (£k)": "£{:.1f}k", "Score": "{:.0f}"}
        )
        st.dataframe(styled, hide_index=True, width='stretch')

    with col_right:
        st.markdown("**Estimated annual revenue by borough**")
        colors = [ACCENT if i < 5 else GREY for i in range(len(BOROUGHS))]
        fig = go.Figure(
            go.Bar(
                x=BOROUGHS["Borough"],
                y=BOROUGHS["Est. revenue (£k)"] * 1000,
                marker_color=colors,
                marker_line_width=0,
            )
        )
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_tickprefix="£",
            yaxis_tickformat=",.0f",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width='stretch')

    st.markdown("**Nightly price distribution — all London listings**")
    fig2 = go.Figure(go.Bar(x=PRICE_DIST["Band"], y=PRICE_DIST["Listings"], marker_color=ACCENT))
    fig2.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig2, width='stretch')

# ==========================================================================
# TAB 2 — PROPERTY TYPES
# ==========================================================================
with tab_properties:
    st.info(
        "**Investment score formula:**  `Score = 0.30·Q + 0.30·I + 0.20·P + 0.10·N − 0.10·M`\n\n"
        "`Q` rating quality · `I` est. revenue (income) · `P` no. of bookings (popularity) · "
        "`N` neighbourhood review quality · `M` no. beds/baths (maintenance cost)"
    )

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
        st.markdown("**Neighbourhood investment score map**")
        st.caption(
            "Choropleth coloured by investment score. In the original app this loads GeoJSON "
            "neighbourhood boundaries from Inside Airbnb at runtime."
        )
        st.container(border=True).markdown(
            "🗺️ **Neighbourhood boundary map** — placeholder.\n\n"
            "Plug in a real choropleth here using `plotly.express.choropleth_mapbox` once you "
            "have GeoJSON boundaries and a `score` column per neighbourhood.\n\n"
            "`Low` 🟥 🟧 🟨 🟩 🟢 `High`"
        )
        st.selectbox(
            "Colour by",
            ["Investment score", "Est. revenue (I)", "Occupancy proxy", "Avg. rating (Q)", "No. bookings (P)"],
        )

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

        st.markdown("**Short-term vs. long-term comparison**")
        st.caption("Monthly returns at median prices. Short-term assumes 90-night cap.")
        fig4 = go.Figure()
        fig4.add_bar(name="Short-term (90-night cap)", x=STL_VS_LTR["Type"],
                      y=STL_VS_LTR["Short-term (90-night cap)"], marker_color=ACCENT)
        fig4.add_bar(name="Long-term rental", x=STL_VS_LTR["Type"],
                      y=STL_VS_LTR["Long-term rental"], marker_color=GREY)
        fig4.update_layout(
            height=200, barmode="group", margin=dict(l=10, r=10, t=10, b=10),
            yaxis_tickprefix="£", legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig4, width='stretch')
        st.caption("Long-term yields from UK HPI / HM Land Registry. Transaction costs excluded.")

# ==========================================================================
# TAB 3 — RECOMMENDATIONS
# ==========================================================================
with tab_recs:
    head_col, btn_col = st.columns([3, 1])
    with head_col:
        st.write(f"Recommendations for: **{investor_profile} · {city} · {room_type}**")
    with btn_col:
        regenerate = st.button("✨ Regenerate", width='stretch')
    if regenerate:
        st.toast("In the original app this would call an LLM to refresh the memo with live data.")

    st.markdown("##### Top 3 recommended boroughs")
    for rec in BOROUGH_RECS:
        with st.container(border=True):
            top_l, top_r = st.columns([4, 1])
            top_l.markdown(f"**{rec['rank']}. {rec['name']}**")
            top_r.markdown(f"`Score: {rec['score']}`")
            st.write(rec["body"])
            with st.expander("🤖 AI rationale"):
                st.write(rec["ai"])

    st.markdown("##### Top 3 recommended property types")
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

# ==========================================================================
# TAB 4 — REVIEW ANALYSIS
# ==========================================================================
with tab_reviews:
    head_col, btn_col = st.columns([3, 1])
    with head_col:
        st.write("Analysing: **Southwark · 1,240 reviews sampled**")
    with btn_col:
        if st.button("✨ Analyse reviews", width='stretch'):
            st.toast("In the original app this would call an LLM to summarise fresh review text.")

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

    st.markdown("**AI review summary**")
    with st.container(border=True):
        st.markdown(AI_REVIEW_SUMMARY)

# ==========================================================================
# TAB 5 — RISKS & ASSUMPTIONS
# ==========================================================================
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
