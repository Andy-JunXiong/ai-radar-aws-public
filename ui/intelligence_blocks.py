import streamlit as st


def render_intelligence_blocks(daily_radar: dict) -> None:
    executive_summary = daily_radar.get("executive_summary", {})
    topic_trends = daily_radar.get("topic_trends", {})
    rising_topics = daily_radar.get("rising_topics", {})
    weekly_momentum = daily_radar.get("weekly_momentum", {})
    strategic_priority = daily_radar.get("strategic_priority", {})

    st.subheader("Executive Summary")

    what_matters_today = executive_summary.get("what_matters_today", "")
    if what_matters_today:
        st.info(what_matters_today)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Importance Signals", executive_summary.get("high_importance_signal_count", 0))
    with col2:
        st.metric("Medium Importance Signals", executive_summary.get("medium_importance_signal_count", 0))
    with col3:
        st.metric("Top Signals", executive_summary.get("top_signal_count", 0))

    st.subheader("Top Topics Today")
    for item in topic_trends.get("top_topics", [])[:5]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            st.write(f"- {item[0]}: {item[1]}")

    st.subheader("Rising Topics")
    for item in rising_topics.get("rising_topics", [])[:5]:
        st.write(
            f"- {item.get('topic', 'Unknown')} "
            f"(count={item.get('topic_count', 0)}, "
            f"high_importance={item.get('high_importance_count', 0)}, "
            f"score={item.get('rising_score', 0)})"
        )

    st.subheader("Weekly Momentum — Rising")
    for item in weekly_momentum.get("rising_this_week", [])[:5]:
        st.write(
            f"- {item.get('topic', 'Unknown')} "
            f"(recent_3d={item.get('recent_3d_count', 0)}, "
            f"earlier_4d={item.get('earlier_4d_count', 0)}, "
            f"delta={item.get('momentum_delta', 0)})"
        )

    st.subheader("Strategic Priority Topics")
    for item in strategic_priority.get("strategic_priority_topics", [])[:5]:
        reasons = ", ".join(item.get("reason", []))
        st.write(
            f"- {item.get('topic', 'Unknown')} "
            f"(priority_score={item.get('priority_score', 0)}, "
            f"reasons={reasons})"
        )