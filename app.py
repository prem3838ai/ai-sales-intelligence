import pandas as pd
import sqlite3
from datetime import date
import plotly.express as px
import streamlit as st

from src.data import validate_sales_data
from src.database import query_sales, DB_PATH, import_csv_to_sqlite
from src.data import DATA_PATH
from src.analytics import kpi_summary, daily_sales, category_summary, build_rfm_segments
from src.forecasting import compare_forecasters

st.set_page_config(page_title="AI Sales Intelligence", page_icon="📈", layout="wide")

st.title("📈 AI Sales Intelligence")
st.caption("Sales performance • Revenue forecasting • Customer intelligence • Near-real-time ingestion")

with st.sidebar:
    st.subheader("Live transaction ingestion")
    st.caption("Add a transaction to SQLite immediately; dashboard refreshes after submission.")
    with st.form("ingest_sale", clear_on_submit=True):
        new_order_id = st.text_input("Order ID", value="LIVE-" + pd.Timestamp.now().strftime("%Y%m%d%H%M%S"))
        new_customer = st.text_input("Customer ID", value="CUST-NEW")
        new_product = st.text_input("Product", value="Wireless Mouse")
        new_category = st.selectbox("Category", ["Electronics", "Home", "Stationery", "Accessories", "Other"])
        new_quantity = st.number_input("Quantity", min_value=1, max_value=100000, value=1)
        new_price = st.number_input("Unit price ($)", min_value=0.0, value=24.99, step=1.0)
        new_cost = st.number_input("Unit cost ($)", min_value=0.0, value=12.0, step=1.0)
        add_sale = st.form_submit_button("Ingest transaction", type="primary")
    if add_sale:
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute("INSERT INTO sales (order_id, order_date, customer_id, product, category, quantity, unit_price, unit_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_order_id.strip(), date.today().isoformat(), new_customer.strip(), new_product.strip(), new_category, int(new_quantity), float(new_price), float(new_cost)))
            get_data.clear()
            st.success("Transaction ingested.")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("That order ID already exists. Use a unique ID.")
    if st.checkbox("Auto-refresh every 30 seconds", value=False):
        st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)

@st.cache_data
def get_data():
    # First-run setup: create the SQLite database automatically from the included demo CSV.
    if not DB_PATH.exists():
        import_csv_to_sqlite(DATA_PATH, DB_PATH)
    df = query_sales()
    validate_sales_data(df)
    return df

try:
    sales = get_data()
except Exception as exc:
    st.error(f"Could not load the sales dataset: {exc}")
    st.stop()

min_date = sales["order_date"].min().date()
max_date = sales["order_date"].max().date()
date_range = st.sidebar.date_input(
    "Order date range", value=(min_date, max_date),
    min_value=min_date, max_value=max_date
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered = sales[
        sales["order_date"].dt.date.between(start_date, end_date)
    ].copy()
else:
    filtered = sales.copy()

if filtered.empty:
    st.warning("No orders found for the selected dates. Choose a wider date range.")
    st.stop()

summary = kpi_summary(filtered)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"${summary['revenue']:,.0f}")
c2.metric("Orders", f"{summary['orders']:,}")
c3.metric("Customers", f"{summary['customers']:,}")
c4.metric("Avg. order value", f"${summary['average_order_value']:,.2f}")

tab_sales, tab_forecast, tab_customers, tab_data = st.tabs(
    ["Sales Overview", "Forecasting", "Customer Intelligence", "Data Explorer"]
)

with tab_sales:
    st.subheader("Revenue over time")
    daily = daily_sales(filtered)
    st.plotly_chart(
        px.line(daily, x="order_date", y="revenue", markers=True,
                title="Daily revenue", labels={"order_date": "Date", "revenue": "Revenue ($)"}),
        use_container_width=True
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(category_summary(filtered), x="category", y="revenue",
                   title="Revenue by category", labels={"category": "Category", "revenue": "Revenue ($)"}),
            use_container_width=True
        )
    with right:
        top_products = (filtered.groupby("product", as_index=False)["revenue"]
                        .sum().sort_values("revenue", ascending=False).head(10))
        st.plotly_chart(
            px.bar(top_products, x="revenue", y="product", orientation="h",
                   title="Top 10 products by revenue",
                   labels={"product": "Product", "revenue": "Revenue ($)"}),
            use_container_width=True
        )

with tab_forecast:
    st.subheader("Future sales forecast")
    st.write("The evaluation uses a chronological holdout, not a random split.")
    horizon = st.slider("Forecast horizon (days)", min_value=7, max_value=30, value=14)
    if st.button("Run forecast comparison", type="primary"):
        with st.spinner("Training and evaluating models..."):
            result = compare_forecasters(filtered, horizon=horizon)
        if result["forecast"].empty:
            st.warning(result["message"])
        else:
            st.metric("Holdout MAE — Random Forest", f"${result['rf_mae']:,.2f}")
            st.metric("Holdout MAE — Naive baseline", f"${result['baseline_mae']:,.2f}")
            st.plotly_chart(
                px.line(result["plot_data"], x="date", y="revenue",
                        color="series", markers=True, title="Actual and forecast revenue",
                        labels={"date": "Date", "revenue": "Revenue ($)", "series": "Series"}),
                use_container_width=True
            )
            st.caption("Forecasts are estimates, not guarantees. Model quality depends on data volume and stability.")
            st.download_button(
                "Download forecast CSV",
                data=result["forecast"].to_csv(index=False).encode("utf-8"),
                file_name="sales_forecast.csv",
                mime="text/csv"
            )
    else:
        st.info("Select a forecast horizon and click **Run forecast comparison**.")

with tab_customers:
    st.subheader("RFM customer segments")
    st.write("RFM = Recency (days since last purchase), Frequency (orders), Monetary (total spend).")
    segments = build_rfm_segments(filtered)
    if segments.empty:
        st.warning("Not enough customer data to create segments.")
    else:
        counts = segments["segment"].value_counts().rename_axis("segment").reset_index(name="customers")
        left, right = st.columns([1, 2])
        with left:
            st.plotly_chart(px.pie(counts, names="segment", values="customers",
                                   title="Customer mix"), use_container_width=True)
        with right:
            st.dataframe(
                segments.groupby("segment", as_index=False)
                .agg(customers=("customer_id", "count"),
                     avg_recency_days=("recency_days", "mean"),
                     avg_orders=("frequency", "mean"),
                     avg_spend=("monetary", "mean"))
                .round(2), use_container_width=True, hide_index=True
            )
        st.download_button(
            "Download customer segments",
            data=segments.to_csv(index=False).encode("utf-8"),
            file_name="customer_segments.csv",
            mime="text/csv"
        )

with tab_data:
    st.subheader("Filtered transaction data")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered sales CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales.csv",
        mime="text/csv"
    )

st.divider()
st.caption("Portfolio project starter • Synthetic demo data • Replace with a documented real dataset before making business claims.")
