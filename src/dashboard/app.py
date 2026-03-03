"""Streamlit dashboard for NHTSA Vehicle Safety Defect Tracker."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent.parent.parent / "data" / "nhtsa_safety.db"


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def main():
    st.set_page_config(
        page_title="NHTSA Vehicle Safety Defect Tracker",
        page_icon="🚗",
        layout="wide",
    )

    st.title("NHTSA Vehicle Safety Defect Tracker")
    st.markdown("Cross-linked database of complaints, recalls, and investigations")

    conn = get_conn()

    # Sidebar navigation
    page = st.sidebar.radio("Navigate", [
        "Overview",
        "Complaint Explorer",
        "Recall Tracker",
        "Investigation Monitor",
        "Vehicle Deep Dive",
        "Safety Trends",
        "Component Analysis",
        "Data Quality",
    ])

    if page == "Overview":
        show_overview(conn)
    elif page == "Complaint Explorer":
        show_complaints(conn)
    elif page == "Recall Tracker":
        show_recalls(conn)
    elif page == "Investigation Monitor":
        show_investigations(conn)
    elif page == "Vehicle Deep Dive":
        show_vehicle_deep_dive(conn)
    elif page == "Safety Trends":
        show_trends(conn)
    elif page == "Component Analysis":
        show_components(conn)
    elif page == "Data Quality":
        show_quality(conn)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Built by Nathan Goldberg** | "
        "nathanmauricegoldberg@gmail.com | "
        "[LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)"
    )


def show_overview(conn):
    """Overview dashboard with KPI cards."""
    st.header("Overview")

    # KPI cards
    complaint_count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    recall_count = conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    inv_count = conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
    link_count = conn.execute("SELECT COUNT(*) FROM cross_links").fetchone()[0]
    crash_count = conn.execute("SELECT COUNT(*) FROM complaints WHERE crash = 1").fetchone()[0]
    death_count = conn.execute("SELECT COALESCE(SUM(num_deaths), 0) FROM complaints").fetchone()[0]
    injury_count = conn.execute("SELECT COALESCE(SUM(num_injuries), 0) FROM complaints").fetchone()[0]
    fire_count = conn.execute("SELECT COUNT(*) FROM complaints WHERE fire = 1").fetchone()[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Complaints", f"{complaint_count:,}")
    c2.metric("Recalls", f"{recall_count:,}")
    c3.metric("Investigations", f"{inv_count:,}")
    c4.metric("Cross-Links", f"{link_count:,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Crashes Reported", f"{crash_count:,}")
    c6.metric("Deaths Reported", f"{death_count:,}")
    c7.metric("Injuries Reported", f"{injury_count:,}")
    c8.metric("Fires Reported", f"{fire_count:,}")

    # Top makes
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Makes by Complaints")
        df = pd.read_sql_query("""
            SELECT make, COUNT(*) as complaints,
                   SUM(crash) as crashes, SUM(fire) as fires,
                   SUM(num_deaths) as deaths
            FROM complaints
            GROUP BY make ORDER BY complaints DESC LIMIT 15
        """, conn)
        if not df.empty:
            fig = px.bar(df, x="make", y="complaints",
                         color="crashes", color_continuous_scale="Reds",
                         title="Complaints by Vehicle Make")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Components")
        df = pd.read_sql_query("""
            SELECT components, COUNT(*) as cnt
            FROM complaints WHERE components != ''
            GROUP BY components ORDER BY cnt DESC LIMIT 15
        """, conn)
        if not df.empty:
            fig = px.bar(df, x="cnt", y="components", orientation="h",
                         title="Most Common Component Complaints")
            fig.update_layout(template="plotly_dark", yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)


def show_complaints(conn):
    """Complaint explorer with search and filter."""
    st.header("Complaint Explorer")

    col1, col2, col3 = st.columns(3)
    with col1:
        makes = pd.read_sql_query(
            "SELECT DISTINCT make FROM complaints ORDER BY make", conn
        )["make"].tolist()
        selected_make = st.selectbox("Make", ["All"] + makes)
    with col2:
        if selected_make != "All":
            models = pd.read_sql_query(
                "SELECT DISTINCT model FROM complaints WHERE make = ? ORDER BY model",
                conn, params=[selected_make]
            )["model"].tolist()
        else:
            models = []
        selected_model = st.selectbox("Model", ["All"] + models)
    with col3:
        crash_only = st.checkbox("Crashes only")
        fire_only = st.checkbox("Fires only")

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if selected_make != "All":
        query += " AND make = ?"
        params.append(selected_make)
    if selected_model != "All":
        query += " AND model = ?"
        params.append(selected_model)
    if crash_only:
        query += " AND crash = 1"
    if fire_only:
        query += " AND fire = 1"
    query += " ORDER BY date_complaint_filed DESC LIMIT 500"

    df = pd.read_sql_query(query, conn, params=params)
    st.write(f"Showing {len(df)} complaints")
    if not df.empty:
        st.dataframe(
            df[["odi_number", "make", "model", "model_year", "crash", "fire",
                "num_injuries", "num_deaths", "date_complaint_filed",
                "components", "summary"]],
            use_container_width=True,
            height=500,
        )


def show_recalls(conn):
    """Recall tracker."""
    st.header("Recall Tracker")

    df = pd.read_sql_query("""
        SELECT campaign_number, manufacturer, make, model, model_year,
               report_received_date, component, summary, consequence,
               num_potentially_affected, park_it
        FROM recalls ORDER BY report_received_date DESC LIMIT 500
    """, conn)

    if df.empty:
        st.info("No recall data loaded yet. Run `python -m src.cli pipeline` with recall fetching enabled.")
        return

    # Park It alerts
    park_it_count = df[df["park_it"] == 1].shape[0]
    if park_it_count > 0:
        st.warning(f"{park_it_count} recalls have 'Park It' (Do Not Drive) advisories")

    affected = df["num_potentially_affected"].sum()
    st.metric("Total Potentially Affected Vehicles", f"{affected:,.0f}")

    st.dataframe(df, use_container_width=True, height=500)


def show_investigations(conn):
    """Investigation monitor."""
    st.header("Investigation Monitor")

    df = pd.read_sql_query("""
        SELECT investigation_number, make, model, model_year_start, model_year_end,
               investigation_type, status, open_date, subject
        FROM investigations ORDER BY open_date DESC LIMIT 500
    """, conn)

    if df.empty:
        st.info("No investigation data loaded yet.")
        return

    # Status breakdown
    col1, col2 = st.columns(2)
    with col1:
        status_df = df["status"].value_counts().reset_index()
        status_df.columns = ["Status", "Count"]
        fig = px.pie(status_df, names="Status", values="Count",
                     title="Investigations by Status")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        type_df = df["investigation_type"].value_counts().reset_index()
        type_df.columns = ["Type", "Count"]
        fig = px.pie(type_df, names="Type", values="Count",
                     title="Investigations by Type")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True, height=400)


def show_vehicle_deep_dive(conn):
    """Deep dive into a specific vehicle."""
    st.header("Vehicle Deep Dive")

    makes = pd.read_sql_query(
        "SELECT DISTINCT make FROM complaints ORDER BY make", conn
    )["make"].tolist()
    selected_make = st.selectbox("Select Make", makes if makes else ["No data"])

    if selected_make and selected_make != "No data":
        models = pd.read_sql_query(
            "SELECT DISTINCT model FROM complaints WHERE make = ? ORDER BY model",
            conn, params=[selected_make],
        )["model"].tolist()
        selected_model = st.selectbox("Select Model", models if models else ["All"])

        if selected_model:
            # Complaints for this vehicle
            complaints_df = pd.read_sql_query("""
                SELECT model_year, COUNT(*) as complaints,
                       SUM(crash) as crashes, SUM(fire) as fires,
                       SUM(num_deaths) as deaths, SUM(num_injuries) as injuries
                FROM complaints WHERE make = ? AND model = ?
                GROUP BY model_year ORDER BY model_year
            """, conn, params=[selected_make, selected_model])

            if not complaints_df.empty:
                st.subheader(f"{selected_make} {selected_model} — Complaints by Year")
                fig = px.bar(complaints_df, x="model_year", y="complaints",
                             color="crashes", color_continuous_scale="Reds",
                             title=f"Complaints by Model Year")
                fig.update_layout(template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                # Component breakdown
                comp_df = pd.read_sql_query("""
                    SELECT components, COUNT(*) as cnt
                    FROM complaints WHERE make = ? AND model = ? AND components != ''
                    GROUP BY components ORDER BY cnt DESC LIMIT 10
                """, conn, params=[selected_make, selected_model])
                if not comp_df.empty:
                    st.subheader("Top Components")
                    fig = px.bar(comp_df, x="cnt", y="components", orientation="h")
                    fig.update_layout(template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)

            # Related recalls
            recalls_df = pd.read_sql_query("""
                SELECT campaign_number, model_year, report_received_date,
                       component, summary, num_potentially_affected
                FROM recalls WHERE make = ? AND model = ?
                ORDER BY report_received_date DESC
            """, conn, params=[selected_make, selected_model])

            if not recalls_df.empty:
                st.subheader(f"Recalls ({len(recalls_df)})")
                st.dataframe(recalls_df, use_container_width=True)


def show_trends(conn):
    """Safety trends over time."""
    st.header("Safety Trends")

    df = pd.read_sql_query("""
        SELECT substr(date_complaint_filed, 1, 7) as month,
               COUNT(*) as complaints,
               SUM(crash) as crashes,
               SUM(fire) as fires,
               SUM(num_deaths) as deaths
        FROM complaints
        WHERE date_complaint_filed != '' AND date_complaint_filed >= '2015-01'
        GROUP BY month ORDER BY month
    """, conn)

    if df.empty:
        st.info("No data available for trends.")
        return

    fig = px.line(df, x="month", y="complaints",
                  title="Monthly Complaint Volume")
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.line(df, x="month", y="crashes",
                      title="Monthly Crashes", color_discrete_sequence=["#E74C3C"])
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(df, x="month", y="fires",
                      title="Monthly Fires", color_discrete_sequence=["#E67E22"])
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)


def show_components(conn):
    """Component analysis."""
    st.header("Component Analysis")

    df = pd.read_sql_query("""
        SELECT components, COUNT(*) as complaints,
               SUM(crash) as crashes, SUM(fire) as fires,
               SUM(num_deaths) as deaths, SUM(num_injuries) as injuries
        FROM complaints WHERE components != ''
        GROUP BY components ORDER BY complaints DESC LIMIT 25
    """, conn)

    if df.empty:
        st.info("No component data available.")
        return

    fig = px.bar(df, x="complaints", y="components", orientation="h",
                 color="deaths", color_continuous_scale="Reds",
                 title="Components by Complaint Volume (colored by deaths)")
    fig.update_layout(template="plotly_dark", height=700,
                      yaxis={"autorange": "reversed"})
    st.plotly_chart(fig, use_container_width=True)

    # Death rate by component
    df["death_rate"] = (df["deaths"] / df["complaints"] * 10000).round(1)
    st.subheader("Death Rate per 10,000 Complaints")
    death_df = df[df["deaths"] > 0].sort_values("death_rate", ascending=False)
    if not death_df.empty:
        fig = px.bar(death_df, x="death_rate", y="components", orientation="h",
                     title="Deaths per 10,000 Complaints by Component")
        fig.update_layout(template="plotly_dark",
                          yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)


def show_quality(conn):
    """Data quality dashboard."""
    st.header("Data Quality")

    for table_name, score_col in [
        ("complaints", "quality_score"),
        ("recalls", "quality_score"),
        ("investigations", "quality_score"),
    ]:
        total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        scored = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {score_col} > 0").fetchone()[0]
        above_threshold = conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE {score_col} >= 0.4"
        ).fetchone()[0]
        avg_score = conn.execute(
            f"SELECT AVG({score_col}) FROM {table_name} WHERE {score_col} > 0"
        ).fetchone()[0] or 0

        st.subheader(f"{table_name.title()}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Records", f"{total:,}")
        c2.metric("Avg Quality Score", f"{avg_score:.3f}")
        c3.metric("Above Threshold", f"{above_threshold:,} ({100*above_threshold/max(total,1):.1f}%)")

    # Cross-link coverage
    st.subheader("Cross-Link Coverage")
    link_types = pd.read_sql_query("""
        SELECT source_type || ' → ' || target_type as link_type,
               link_method, COUNT(*) as count,
               ROUND(AVG(confidence), 3) as avg_confidence
        FROM cross_links
        GROUP BY source_type, target_type, link_method
        ORDER BY count DESC
    """, conn)
    if not link_types.empty:
        st.dataframe(link_types, use_container_width=True)
    else:
        st.info("No cross-links generated yet.")


if __name__ == "__main__":
    main()
