class AppContext:
    """Stores context and shared resources."""
    def __init__(self, config, font_path, redis_db, stop_event):
        self.config = config
        self.font_path = font_path
        self.redis_db = redis_db
        self.stop_event = stop_event
