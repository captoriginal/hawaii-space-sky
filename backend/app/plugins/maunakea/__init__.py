def register(app):
    """
    Maunakea panel relies on shared /api/status data only. We provide an empty
    register hook so the plugin loader can import the package cleanly and so
    future Maunakea-specific routes can be added here without changing the host.
    """

    return None
