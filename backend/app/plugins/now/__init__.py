def register(app):
    """
    Now/alerts panel consumes the shared /api/status payload so it does not
    currently expose plugin-specific backend routes. The register hook is kept
    both to satisfy the plugin loader and to provide a place for future API
    endpoints should the panel need bespoke data.
    """

    return None
