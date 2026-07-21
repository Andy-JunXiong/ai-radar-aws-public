def filter_signals(signals, source_stats):
    filtered = []

    for s in signals:
        source = s.get("source", "unknown")
        quality = source_stats.get(source, {}).get("quality_score", 0)

# Core rules (tunable)
        if quality >= 0.8:
            s["quality_level"] = "high"
            filtered.append(s)
        elif quality >= 0.5:
            s["quality_level"] = "medium"
            filtered.append(s)
        else:
            s["quality_level"] = "low"
        # The caller may choose to discard or retain it.
        # Retain it for now, but mark it.
            filtered.append(s)

    return filtered
