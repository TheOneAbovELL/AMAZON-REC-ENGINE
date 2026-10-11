"""Streamlit analyst console: run queries against the Python engine and inspect every signal.

    pip install -r requirements-dashboard.txt
    streamlit run app.py

The shopper-facing UI is the Next.js app (pages/); this console is for examining rankings.
"""

import json

import pandas as pd
import streamlit as st

from src.config import load_settings
from src.recommender import Filters, RecommendationEngine


@st.cache_resource(show_spinner="Loading catalog and embedding model…")
def load_engine() -> RecommendationEngine:
    return RecommendationEngine.load(load_settings())


@st.cache_data
def load_meta() -> dict:
    with open(load_settings().catalog_meta_path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    st.set_page_config(page_title="Recommendation engine console", layout="wide")
    engine = load_engine()
    meta = load_meta()
    status = engine.status()

    st.title("Recommendation engine console")
    st.caption(
        f"{status['products']:,} products · snapshot {meta.get('snapshot')} · mode **{status['mode']}**"
        + (f" ({status['model']})" if status["model"] else "")
    )
    if status["notice"]:
        st.warning(status["notice"])

    with st.sidebar:
        profiles = engine.profiles()
        profile = st.selectbox("Shopper profile", list(profiles), format_func=lambda p: profiles[p]["label"])
        departments = ["All"] + [d["name"] for d in meta["departments"]]
        department = st.selectbox("Department", departments)
        max_price = st.number_input("Max price (₹, 0 = none)", min_value=0, step=500)
        min_rating = st.slider("Minimum rating", 0.0, 5.0, 0.0, 0.5)
        top_k = st.slider("Results", 5, 30, 10)
        use_dense = st.checkbox("Use semantic retrieval", value=engine.dense is not None, disabled=engine.dense is None)

    query = st.text_input("Query", "noise cancelling headphones")
    if not query.strip():
        st.info("Enter a query.")
        return

    filters = Filters(
        department=None if department == "All" else department,
        max_price=float(max_price) or None,
        min_rating=min_rating or None,
    )
    response = engine.recommend(query, profile, top_k, filters, use_dense=use_dense)
    st.json(response["interpretation"], expanded=False)
    st.write(f"{len(response['results'])} of {response['total_matches']} relevant products in {response['took_ms']} ms")
    if response.get("message"):
        st.info(response["message"])
    if not response["results"]:
        return

    rows = [
        {
            "rank": i,
            "name": r["name"],
            "price": r["price"],
            "rating": r["rating"],
            "ratings": r["rating_count"],
            "score": r["score"],
            **{f"sig_{k}": v for k, v in r["signals"].items()},
        }
        for i, r in enumerate(response["results"], start=1)
    ]
    table = pd.DataFrame(rows).set_index("rank")
    st.dataframe(table, width="stretch")
    st.subheader("Score contributions")
    st.bar_chart(pd.DataFrame([r["contributions"] for r in response["results"]], index=table.index))

    for i, r in enumerate(response["results"], start=1):
        with st.expander(f"{i}. {r['name']}"):
            st.write("\n".join(f"- {reason}" for reason in r["reasons"]))
            st.markdown(f"[View on amazon.in]({r['product_url']})")


if __name__ == "__main__":
    main()
