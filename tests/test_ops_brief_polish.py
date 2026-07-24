
def test_mongodb_matrix_factual_wording():
    from app.ops_brief import service_matrix_from_snapshot

    snap = {
        "source": "ralfia_bridge_live",
        "ralfia_status": {
            "mongodb_ok": True,
            "mongodb_db": "db",
            "mongodb_clients": 37,
            "mongodb_pipeline_items": 24,
            "http_port": 8101,
            "mcp_port": 8102,
            "service_label": "raphiia-openai",
        },
        "health": "up",
        "system_state": "active",
        "service": "Evolution API",
        "node_label": ".4",
    }
    m = service_matrix_from_snapshot(snap)
    mongo_line = next(x for x in m["up"] if "MongoDB" in x)
    assert "reachable" in mongo_line.lower()
    assert "37" in mongo_line
    assert "do not prove health" in mongo_line.lower() or "counts alone" in mongo_line.lower()
