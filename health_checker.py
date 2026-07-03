import json
import threading
import time
from datetime import datetime, timezone

from config_manager import (
    PROFILES_DIR,
    _sync_key_to_openclaw,
    _remove_from_openclaw,
    get_vendor,
    get_vendors,
    reconcile_openclaw,
    update_key_data,
)
from providers import get_provider, pick_default_model, probe_provider, scan_models

HEALTH_CACHE_PATH = PROFILES_DIR / "health_cache.json"
_lock = threading.Lock()


def _load_cache() -> dict:
    if HEALTH_CACHE_PATH.exists():
        with open(HEALTH_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(HEALTH_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def check_key_health(vendor_id: str, key_id: str, scan_models_flag: bool = True) -> dict:
    vendor = get_vendor(vendor_id)
    if not vendor:
        return {"key_id": key_id, "healthy": False, "latency_ms": 0, "error": "Vendor not found"}

    key_entry = None
    for k in vendor.get("keys", []):
        if k["id"] == key_id:
            key_entry = k
            break
    if not key_entry:
        return {"key_id": key_id, "healthy": False, "latency_ms": 0, "error": "Key not found"}

    api_url = vendor["api_url"]
    api_key = key_entry["api_key"]
    provider_id = vendor.get("provider", "openai")
    prov = get_provider(provider_id)
    check_type = prov["check_type"] if prov else "openai_chat"

    start = time.time()
    healthy, error_msg = probe_provider(check_type, api_url, api_key)
    latency_ms = int((time.time() - start) * 1000)

    models = []
    default_model = key_entry.get("default_model", "")
    if healthy and scan_models_flag:
        models = scan_models(check_type, api_url, api_key)
        if not default_model and models:
            default_model = pick_default_model(models)

    cache_key = f"{vendor_id}:{key_id}"
    result = {
        "key_id": key_id,
        "vendor_id": vendor_id,
        "healthy": healthy,
        "latency_ms": latency_ms,
        "error": None if healthy else error_msg,
        "message": error_msg if healthy else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "default_model": default_model,
    }

    with _lock:
        cache = _load_cache()
        cache[cache_key] = result
        _save_cache(cache)

    return result


def check_all_keys() -> list[dict]:
    results = []
    reconcile_openclaw()

    for v in get_vendors():
        for k in v.get("keys", []):
            health = check_key_health(v["id"], k["id"])
            results.append(health)
            if health.get("healthy"):
                models = health.get("models", [])
                default_model = health.get("default_model", "")
                updates = {"enabled": True}
                if models:
                    updates["models"] = models
                if default_model:
                    updates["default_model"] = default_model
                update_key_data(v["id"], k["id"], **updates)
                _sync_key_to_openclaw(v, k, models_override=models)
            else:
                ocp_key = f"{v['provider']}:{k['name']}"
                _remove_from_openclaw(ocp_key)
                old = f"{v['provider']}-{k['id']}"
                if old != ocp_key:
                    _remove_from_openclaw(old)
                update_key_data(v["id"], k["id"], enabled=False)

    reconcile_openclaw()
    return results


def get_all_health_status() -> dict:
    results = {}
    with _lock:
        cache = _load_cache()
    for v in get_vendors():
        for k in v.get("keys", []):
            ck = f"{v['id']}:{k['id']}"
            results[ck] = cache.get(ck, {
                "key_id": k["id"],
                "vendor_id": v["id"],
                "healthy": None,
                "latency_ms": 0,
                "error": "Not checked yet",
            })
    return results
