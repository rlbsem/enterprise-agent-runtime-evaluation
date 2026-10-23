"""Local release routing into the actual runtime, including mandatory read-only canaries."""
from .engine import Engine


def routed_run(registry, store, server, factories, case, key, candidate=None):
    route = registry.route(key, case, candidate)
    model = factories[route["version"]]()
    shadow = route["mode"] == "shadow"
    engine = Engine(store, model, server["url"], server["read_token"],
                    "" if shadow else server["write_token"], shadow=shadow)
    rid = store.create("acme", case, model.mode)
    with store.tx() as c:
        store.log(c, rid, "release_route", route)
    run = engine.drive(rid, reviewer=not shadow)
    return {"route": route, "status": run["status"], "trace": store.trace(rid)}
