import logging
import sys
import threading
import traceback

from flask import Flask, jsonify, render_template, request, make_response

from batch_import import parse_batch_text
from providers import get_providers, recognize_provider
from config_manager import (
    add_key,
    add_vendor,
    delete_key,
    delete_vendor,
    get_gateway_status,
    get_key,
    get_keys,
    get_settings,
    get_vendor,
    get_vendors,
    reconcile_openclaw,
    restart_gateway,
    sync_from_openclaw,
    update_key,
    update_key_data,
    update_settings,
    update_vendor,
    _sync_key_to_openclaw,
    _remove_from_openclaw,
)
from health_checker import (
    check_all_keys,
    check_key_health,
    get_all_health_status,
)
from i18n import SUPPORTED_LANGS, get_translations, resolve_lang, t as _t

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="[manager] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "not found"}), 404

@app.errorhandler(500)
def handle_500(e):
    log.error("Server error: %s", traceback.format_exc())
    return jsonify({"error": "internal server error"}), 500


def _current_lang():
    return resolve_lang(
        request.headers.get("Accept-Language"),
        request.cookies.get("lang"),
    )


_sr = sync_from_openclaw()
log.info("Synced %d keys from OpenClaw config (total: %d)", _sr["synced"], _sr["total"])


@app.route("/")
def index():
    lang = _current_lang()
    all_locales = {l: get_translations(l) for l in SUPPORTED_LANGS}
    merged = {**all_locales["en"], **all_locales[lang]}
    resp = make_response(render_template(
        "index.html",
        lang=lang,
        supported_langs=SUPPORTED_LANGS,
        t=lambda key: merged.get(key, key),
        all_locales=all_locales,
    ))
    resp.set_cookie("lang", lang, max_age=86400 * 365)
    return resp


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ── Vendors ──────────────────────────────────────────────

@app.route("/api/providers", methods=["GET"])
def api_list_providers():
    return jsonify({"providers": get_providers()})


@app.route("/api/providers/recognize", methods=["POST"])
def api_recognize_provider():
    data = request.get_json() or {}
    text = data.get("text", "")
    matched = recognize_provider(text)
    if matched:
        return jsonify(matched)
    return jsonify(None)


@app.route("/api/vendors", methods=["GET"])
def api_list_vendors():
    vendors = get_vendors()
    health = get_all_health_status()
    return jsonify({"vendors": vendors, "health": health})


@app.route("/api/vendors", methods=["POST"])
def api_create_vendor():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    v = add_vendor(
        name=data["name"],
        provider=data.get("provider", "custom"),
        api_url=data.get("api_url", "https://api.openai.com/v1"),
    )
    return jsonify(v), 201


@app.route("/api/vendors/<vendor_id>", methods=["PUT"])
def api_update_vendor(vendor_id):
    data = request.get_json() or {}
    v = update_vendor(vendor_id, **data)
    if not v:
        return jsonify({"error": "not found"}), 404
    return jsonify(v)


@app.route("/api/vendors/<vendor_id>", methods=["DELETE"])
def api_delete_vendor(vendor_id):
    if delete_vendor(vendor_id):
        return jsonify({"success": True})
    return jsonify({"error": "not found"}), 404


# ── Keys ─────────────────────────────────────────────────

@app.route("/api/vendors/<vendor_id>/keys", methods=["GET"])
def api_list_keys(vendor_id):
    keys = get_keys(vendor_id)
    if keys is None:
        return jsonify({"error": "vendor not found"}), 404
    return jsonify({"keys": keys})


@app.route("/api/vendors/<vendor_id>/keys", methods=["POST"])
def api_create_key(vendor_id):
    data = request.get_json()
    if not data or not data.get("name") or not data.get("api_key"):
        return jsonify({"error": "name and api_key are required"}), 400
    k = add_key(vendor_id, data["name"], data["api_key"])
    if not k:
        return jsonify({"error": "vendor not found"}), 404

    health = check_key_health(vendor_id, k["id"])
    v = get_vendor(vendor_id)
    if health.get("healthy"):
        models = health.get("models", [])
        default_model = health.get("default_model", "")
        updates = {"enabled": True}
        if models:
            updates["models"] = models
        if default_model:
            updates["default_model"] = default_model
        update_key_data(vendor_id, k["id"], **updates)
        _sync_key_to_openclaw(v, k, models_override=models)
    else:
        _remove_from_openclaw(f"{v['provider']}:{k['name']}")
        old = f"{v['provider']}-{k['id']}"
        if old != f"{v['provider']}:{k['name']}":
            _remove_from_openclaw(old)
        update_key_data(vendor_id, k["id"], enabled=False)
        k["enabled"] = False

    return jsonify({"key": k, "health": health}), 201


@app.route("/api/vendors/<vendor_id>/keys/<key_id>", methods=["PUT"])
def api_update_key(vendor_id, key_id):
    data = request.get_json() or {}
    k = update_key(vendor_id, key_id, **data)
    if not k:
        return jsonify({"error": "not found"}), 404
    return jsonify(k)


@app.route("/api/vendors/<vendor_id>/keys/<key_id>", methods=["DELETE"])
def api_delete_key(vendor_id, key_id):
    if delete_key(vendor_id, key_id):
        return jsonify({"success": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/vendors/<vendor_id>/keys/<key_id>/health", methods=["GET"])
def api_check_key_health(vendor_id, key_id):
    health = check_key_health(vendor_id, key_id)
    v = get_vendor(vendor_id)
    k = get_key(vendor_id, key_id)
    if v and k and health.get("healthy"):
        models = health.get("models", [])
        default_model = health.get("default_model", "")
        updates = {"enabled": True}
        if models:
            updates["models"] = models
        if default_model:
            updates["default_model"] = default_model
        update_key_data(vendor_id, key_id, **updates)
        _sync_key_to_openclaw(v, k, models_override=models)
    elif v and k and not health.get("healthy"):
        _remove_from_openclaw(f"{v['provider']}:{k['name']}")
        old = f"{v['provider']}-{k['id']}"
        if old != f"{v['provider']}:{k['name']}":
            _remove_from_openclaw(old)
        update_key_data(vendor_id, key_id, enabled=False)
    return jsonify(health)


@app.route("/api/vendors/<vendor_id>/keys/<key_id>/enable", methods=["POST"])
def api_enable_key(vendor_id, key_id):
    v = get_vendor(vendor_id)
    k = get_key(vendor_id, key_id)
    if not v or not k:
        return jsonify({"error": "not found"}), 404
    k = update_key(vendor_id, key_id, enabled=True)
    _sync_key_to_openclaw(v, k)
    return jsonify(k)


@app.route("/api/vendors/<vendor_id>/keys/<key_id>/disable", methods=["POST"])
def api_disable_key(vendor_id, key_id):
    v = get_vendor(vendor_id)
    k = get_key(vendor_id, key_id)
    if not v or not k:
        return jsonify({"error": "not found"}), 404
    _remove_from_openclaw(f"{v['provider']}:{k['name']}")
    old = f"{v['provider']}-{k['id']}"
    if old != f"{v['provider']}:{k['name']}":
        _remove_from_openclaw(old)
    k = update_key(vendor_id, key_id, enabled=False)
    return jsonify(k)


@app.route("/api/vendors/<vendor_id>/keys/batch", methods=["POST"])
def api_batch_keys(vendor_id):
    data = request.get_json() or {}
    key_ids = data.get("key_ids", [])
    action = data.get("action", "")
    if not key_ids or action not in ("enable", "disable", "delete"):
        return jsonify({"error": "key_ids and action (enable/disable/delete) required"}), 400
    v = get_vendor(vendor_id)
    if not v:
        return jsonify({"error": "vendor not found"}), 404
    results = []
    for kid in key_ids:
        k = get_key(vendor_id, kid)
        if not k:
            results.append({"key_id": kid, "success": False, "error": "not found"})
            continue
        if action == "enable":
            _sync_key_to_openclaw(v, k)
            update_key(vendor_id, kid, enabled=True)
            results.append({"key_id": kid, "success": True, "action": "enabled"})
        elif action == "disable":
            _remove_from_openclaw(f"{v['provider']}:{k['name']}")
            old = f"{v['provider']}-{k['id']}"
            if old != f"{v['provider']}:{k['name']}":
                _remove_from_openclaw(old)
            update_key(vendor_id, kid, enabled=False)
            results.append({"key_id": kid, "success": True, "action": "disabled"})
        elif action == "delete":
            delete_key(vendor_id, kid)
            results.append({"key_id": kid, "success": True, "action": "deleted"})
    return jsonify({"results": results, "count": len(results)})


# ── Health ───────────────────────────────────────────────

@app.route("/api/health/check-all", methods=["POST"])
def api_health_check_all():
    results = check_all_keys()
    return jsonify({"results": results})


# ── Batch Import ─────────────────────────────────────────

@app.route("/api/batch-import/parse", methods=["POST"])
def api_batch_parse():
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "text is required"}), 400
    entries = parse_batch_text(text)
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/batch-import/apply", methods=["POST"])
def api_batch_apply():
    data = request.get_json() or {}
    entries = data.get("entries", [])
    if not entries:
        return jsonify({"error": "entries are required"}), 400
    created = []
    for entry in entries:
        provider = entry.get("provider", "unknown")
        api_url = entry.get("api_url", "")
        api_key = entry.get("api_key", "")
        name = entry.get("name", api_key[:12])

        if not api_key or not api_url:
            continue

        vendor = None
        for v in get_vendors():
            if v["provider"] == provider:
                vendor = v
                break

        if not vendor:
            vendor = add_vendor(
                name=provider.replace("-", " ").title(),
                provider=provider,
                api_url=api_url,
            )

        key_exists = any(k["name"] == name or k["api_key"] == api_key for k in vendor.get("keys", []))
        if not key_exists:
            k = add_key(vendor["id"], name, api_key)
            if k:
                _sync_key_to_openclaw(vendor, k)
                created.append({"vendor": vendor["name"], "key": name, "api_key": api_key[:8] + "..."})
        else:
            created.append({"vendor": vendor["name"], "key": name, "api_key": api_key[:8] + "...", "skipped": True})

    return jsonify({"created": created, "count": len(created)})


# ── Sync ─────────────────────────────────────────────────

@app.route("/api/sync", methods=["POST"])
def api_sync():
    result = sync_from_openclaw()
    return jsonify(result)


# ── Gateway ──────────────────────────────────────────────

@app.route("/api/gateway/status", methods=["GET"])
def api_gateway_status():
    from config_manager import get_openclaw_version, MANAGER_VERSION, MIN_OPENCLAW_VERSION, RECOMMENDED_OPENCLAW_VERSION
    status = get_gateway_status()
    health = get_all_health_status()
    status["health"] = health
    status["openclaw_version"] = get_openclaw_version()
    status["manager_version"] = MANAGER_VERSION
    status["min_openclaw_version"] = MIN_OPENCLAW_VERSION
    status["recommended_openclaw_version"] = RECOMMENDED_OPENCLAW_VERSION
    return jsonify(status)


@app.route("/api/gateway/restart", methods=["POST"])
def api_gateway_restart():
    lang = _current_lang()
    result = restart_gateway()
    if result.get("success"):
        result["message"] = _t("alert.restartSuccess", lang)
    else:
        result["message"] = result.get("message") or _t("alert.restartFailed", lang)
    return jsonify(result)


@app.route("/api/gateway/config", methods=["GET"])
def api_get_gateway_config():
    from config_manager import get_settings
    settings = get_settings()
    return jsonify(settings.get("gateway", {"mode": "local"}))


@app.route("/api/gateway/config", methods=["POST"])
def api_save_gateway_config():
    from config_manager import update_settings
    data = request.get_json() or {}
    update_settings(gateway=data)
    return jsonify({"ok": True})


@app.route("/api/gateway/remote/test", methods=["POST"])
def api_test_remote_gateway():
    from remote import ssh_test_connection, gateway_test_connection
    data = request.get_json() or {}
    conn_type = data.get("type", "")
    if conn_type == "ssh":
        return jsonify(ssh_test_connection(data))
    elif conn_type == "gateway":
        return jsonify(gateway_test_connection(data))
    return jsonify({"success": False, "message": "unknown type"})


# ── Settings ─────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(get_settings())


@app.route("/api/settings", methods=["POST"])
def api_update_settings():
    data = request.get_json() or {}
    s = update_settings(**data)
    return jsonify(s)


@app.route("/api/lang", methods=["POST"])
def api_set_lang():
    data = request.get_json() or {}
    lang = data.get("lang", "en")
    resp = jsonify({"lang": lang})
    resp.set_cookie("lang", lang, max_age=86400 * 365)
    return resp


if __name__ == "__main__":
    import webbrowser
    import os

    default_port = int(os.environ.get("OPENCLAW_MANAGER_PORT", "8787"))
    port = default_port
    last_err = None

    for _ in range(20):
        try:
            url = f"http://127.0.0.1:{port}"
            print(f" OpenClaw Manager running at {url}")
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            reconcile_openclaw()
            app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)
            break
        except OSError as e:
            last_err = e
            log.warning("Port %d in use, trying %d...", port, port + 1)
            port += 1
        except Exception as e:
            last_err = e
            break

    if last_err:
        log.error("Failed to start: %s", last_err)
        print(f"\n Failed to start server: {last_err}")
        print(f" Try: OPENCLAW_MANAGER_PORT=<port> python3 app.py")
        sys.exit(1)
