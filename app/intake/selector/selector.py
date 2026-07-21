from intake.schemas import Signal

def select_top_signals(signals: list[Signal], top_n: int = 5) -> list[Signal]:
    ranked = sorted(signals, key=lambda x: x.scores.total, reverse=True)
    return ranked[:top_n]