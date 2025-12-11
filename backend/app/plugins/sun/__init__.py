def register(app):
    """
    Sun panel currently consumes shared /api/status data, so no backend routes
    are required. The register hook exists to satisfy the plugin loader and to
    provide a future place for sun-specific endpoints if needed.
    """

    return None
