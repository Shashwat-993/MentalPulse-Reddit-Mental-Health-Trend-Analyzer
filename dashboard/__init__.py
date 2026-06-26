"""MentalPulse dashboard (Streamlit).

A local-runnable Streamlit app showing aggregate sentiment and crisis-signal
trends across public Reddit mental-health communities, plus a preview analyst
panel. The UI talks to a small data-access seam (``dashboard.data``) that serves
deterministic sample data today and swaps to live Gold/Snowflake once the
pipeline lands — see the architecture's "Streamlit-in-Snowflake with a local
fallback" design.

Run from the repo root:

    streamlit run dashboard/app.py
"""
