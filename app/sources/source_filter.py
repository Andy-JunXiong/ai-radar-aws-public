def filter_signals(signals, source_stats):
    filtered = []

    for s in signals:
        source = s.get("source", "unknown")
        quality = source_stats.get(source, {}).get("quality_score", 0)

        # 核心规则（可调）
        if quality >= 0.8:
            s["quality_level"] = "high"
            filtered.append(s)
        elif quality >= 0.5:
            s["quality_level"] = "medium"
            filtered.append(s)
        else:
            s["quality_level"] = "low"
            # 可以选择丢弃或保留
            # 先保留，但标记
            filtered.append(s)

    return filtered