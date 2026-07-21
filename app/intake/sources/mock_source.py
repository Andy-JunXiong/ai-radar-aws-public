from intake.schemas import Signal

def collect_mock_signals() -> list[Signal]:
    signals = [
        Signal(
            id="signal_001",
            title="AI agents are shifting from prompt wrappers to system architectures",
            url="https://example.com/agent-architecture",
            source="Mock Blog",
            source_type="blog",
            published_at="2026-03-20",
            raw_text="""
            AI agents are no longer simple prompt wrappers.
            The field is moving toward full-stack agent systems including routing,
            memory, tool use, execution layers, and feedback loops.
            This shift matters because building production AI systems now requires
            architecture thinking rather than isolated prompting skills.
            """.strip(),
        ),
        Signal(
            id="signal_002",
            title="Why input quality is becoming the bottleneck of AI systems",
            url="https://example.com/input-quality",
            source="Mock Blog",
            source_type="blog",
            published_at="2026-03-20",
            raw_text="""
            Many AI systems fail not because the model is weak,
            but because the input layer is noisy, unstable, and poorly structured.
            Teams are increasingly building preprocessing, ranking, filtering,
            and context injection systems to improve downstream output quality.
            """.strip(),
        ),
    ]
    return signals