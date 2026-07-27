def format_seconds(seconds: float) -> str:
    minutes, sec = divmod(max(seconds, 0.0), 60)
    return f"{int(minutes):02d}:{sec:06.3f}"
