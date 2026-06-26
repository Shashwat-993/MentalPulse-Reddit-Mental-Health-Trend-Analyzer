"""MentalPulse dashboard — Streamlit-in-Snowflake deployment target (Phase 4).

The dashboard itself is implemented and runnable locally at
``dashboard/app.py``:

    streamlit run dashboard/app.py

It serves aggregate sentiment / crisis-signal trends and a preview analyst
panel, driven by a swappable data-access layer (``dashboard/data.py``) that uses
sample data today and live Gold/Snowflake once the pipeline lands.

This module is the **Streamlit-in-Snowflake** deployment variant: the same
panels, but reading Gold through a Snowpark session instead of the local data
layer (Streamlit-in-Snowflake has no local filesystem and authenticates via the
active session). Wiring that Snowpark data source is finalized in Phase 4.
"""

from __future__ import annotations


def main() -> None:
    # TODO(Phase 4): render the dashboard panels using a Snowpark-backed data
    # source (get_active_session() -> Gold tables) and deploy as a
    # Streamlit-in-Snowflake app. For local use, run dashboard/app.py instead.
    raise NotImplementedError(
        "Streamlit-in-Snowflake deployment is finalized in Phase 4; "
        "run dashboard/app.py for the local dashboard."
    )


if __name__ == "__main__":
    main()
