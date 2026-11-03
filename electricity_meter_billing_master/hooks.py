def post_init_hook(env):
    """Give every zone that already exists its report line (zones created later get theirs on creation)."""
    zones = env['res.zone'].with_context(active_test=False).search([])
    env['res.zone.report']._ensure_for_zones(zones)
