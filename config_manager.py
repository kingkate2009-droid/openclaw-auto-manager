import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

OPENCLAW_CONFIG_DIR = Path.home() / ".openclaw"
OPENCLAW_CONFIG_PATH = OPENCLAW_CONFIG_DIR / "openclaw.json"
AGENT_DIR = OPENCLAW_CONFIG_DIR / "agents" / "main" / "agent"
AGENT_AUTH_PATH = AGENT_DIR / "auth-profiles.json"
AGENT_MODELS_PATH = AGENT_DIR / "models.json"
AGENT_SQLITE_PATH = AGENT_DIR / "openclaw-agent.sqlite"
PROFILES_DIR = Path.home() / ".openclaw-auto-manager"
DATA_PATH = PROFILES_DIR / "data.json"


def _ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _load_data() -> dict:
    _ensure_dirs()
    if DATA_PATH.exists():
        with open(DATA_PATH) as f:
            return json.load(f)
    return {"vendors": [], "settings": {"check_interval_seconds": 300}}


def _save_data(data: dict) -> None:
    _ensure_dirs()
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _next_id(items: list) -> str:
    return str(max((int(i.get("id", 0)) for i in items), default=0) + 1)


def _load_openclaw_config() -> dict:
    if not OPENCLAW_CONFIG_PATH.exists():
        return {}
    with open(OPENCLAW_CONFIG_PATH) as f:
        raw = f.read()
    try:
        import json5
        return json5.loads(raw)
    except ImportError:
        return json.loads(raw)
    except Exception:
        return {}


def _save_openclaw_config(cfg: dict) -> None:
    if "models" not in cfg:
        cfg["models"] = {}
    if "providers" not in cfg["models"]:
        cfg["models"]["providers"] = {}

    backup = OPENCLAW_CONFIG_PATH.with_suffix(".json.bak")
    shutil.copy2(OPENCLAW_CONFIG_PATH, backup)

    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(OPENCLAW_CONFIG_DIR), suffix=".json", delete=False
    ) as f:
        json.dump(cfg, f, indent=2)
        tmp = f.name
    os.replace(tmp, str(OPENCLAW_CONFIG_PATH))
    if backup.exists():
        backup.unlink()


def _load_auth_profiles() -> dict:
    if not AGENT_AUTH_PATH.exists():
        return {"version": 1, "profiles": {}}
    with open(AGENT_AUTH_PATH) as f:
        return json.load(f)


def _save_auth_profiles(data: dict) -> None:
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AGENT_AUTH_PATH, "w") as f:
        json.dump(data, f, indent=2)
    _sync_auth_to_sqlite(data)


def _sync_auth_to_sqlite(auth_data: dict) -> None:
    if not AGENT_SQLITE_PATH.exists():
        return
    try:
        store_json = json.dumps(auth_data)
        now_ms = int(time.time() * 1000)
        with sqlite3.connect(str(AGENT_SQLITE_PATH)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO auth_profile_store (store_key, store_json, updated_at) VALUES (?, ?, ?)",
                ("primary", store_json, now_ms),
            )
            conn.commit()
    except Exception:
        pass


def _load_agent_models() -> dict:
    if not AGENT_MODELS_PATH.exists():
        return {"providers": {}}
    with open(AGENT_MODELS_PATH) as f:
        return json.load(f)


def _save_agent_models(data: dict) -> None:
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AGENT_MODELS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Vendors ──────────────────────────────────────────────

def get_vendors() -> list[dict]:
    return _load_data().get("vendors", [])


def get_vendor(vendor_id: str) -> Optional[dict]:
    for v in get_vendors():
        if v["id"] == vendor_id:
            return v
    return None


def add_vendor(name: str, provider: str, api_url: str, endpoint_type: str = "openai") -> dict:
    data = _load_data()
    vendor = {
        "id": _next_id(data.get("vendors", [])),
        "name": name,
        "provider": provider,
        "api_url": api_url.rstrip("/"),
        "endpoint_type": endpoint_type,  # "openai" or "anthropic"
        "keys": [],
    }
    data["vendors"].append(vendor)
    _save_data(data)
    return vendor


def update_vendor(vendor_id: str, **kwargs) -> Optional[dict]:
    data = _load_data()
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            for key in ("name", "provider", "api_url", "endpoint_type"):
                if key in kwargs:
                    v[key] = kwargs[key]
            if "api_url" in kwargs:
                v["api_url"] = kwargs["api_url"].rstrip("/")
            _save_data(data)
            return v
    return None


def delete_vendor(vendor_id: str) -> bool:
    data = _load_data()
    removed = None
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            removed = v
            break
    data["vendors"] = [v for v in data["vendors"] if v["id"] != vendor_id]
    if len(data["vendors"]) == len(_load_data()["vendors"]):
        return False
    _save_data(data)
    if removed:
        for k in removed.get("keys", []):
            _remove_from_openclaw(f"{removed['provider']}@{k['name']}")
            old = f"{removed['provider']}-{k['id']}"
            if old != f"{removed['provider']}@{k['name']}":
                _remove_from_openclaw(old)
    return True


# ── Keys ─────────────────────────────────────────────────

def get_keys(vendor_id: str) -> list[dict]:
    v = get_vendor(vendor_id)
    return v.get("keys", []) if v else []


def get_key(vendor_id: str, key_id: str) -> Optional[dict]:
    for k in get_keys(vendor_id):
        if k["id"] == key_id:
            return k
    return None


def add_key(vendor_id: str, name: str, api_key: str) -> Optional[dict]:
    data = _load_data()
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            entry = {
                "id": _next_id(v.get("keys", [])),
                "name": name,
                "api_key": api_key,
                "enabled": True,
            }
            v["keys"].append(entry)
            _save_data(data)
            return entry
    return None


def update_key(vendor_id: str, key_id: str, **kwargs) -> Optional[dict]:
    data = _load_data()
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            for k in v["keys"]:
                if k["id"] == key_id:
                    for key in ("name", "api_key", "enabled", "models", "default_model"):
                        if key in kwargs:
                            k[key] = kwargs[key]
                    _save_data(data)
                    if k.get("enabled", True):
                        _sync_key_to_openclaw(v, k)
                    else:
                        _remove_from_openclaw(f"{v['provider']}@{k['name']}")
                        old = f"{v['provider']}-{k['id']}"
                        if old != f"{v['provider']}@{k['name']}":
                            _remove_from_openclaw(old)
                        # Remove from agents.defaults.models
                        cfg = _load_openclaw_config()
                        defaults_models = cfg.get("agents", {}).get("defaults", {}).get("models", {})
                        for model_ref in list(defaults_models.keys()):
                            if model_ref.startswith(f"{v['provider']}/"):
                                del defaults_models[model_ref]
                        _save_openclaw_config(cfg)
                    return k
    return None


def update_key_data(vendor_id: str, key_id: str, **kwargs) -> Optional[dict]:
    """Update key data without syncing to OpenClaw."""
    data = _load_data()
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            for k in v["keys"]:
                if k["id"] == key_id:
                    for key in ("name", "api_key", "enabled", "models", "default_model"):
                        if key in kwargs:
                            k[key] = kwargs[key]
                    _save_data(data)
                    return k
    return None


def delete_key(vendor_id: str, key_id: str) -> bool:
    data = _load_data()
    for v in data["vendors"]:
        if v["id"] == vendor_id:
            removed = None
            for k in v["keys"]:
                if k["id"] == key_id:
                    removed = k
                    break
            v["keys"] = [k for k in v["keys"] if k["id"] != key_id]
            _save_data(data)
            if removed:
                _remove_from_openclaw(f"{v['provider']}:{removed['name']}")
                old = f"{v['provider']}-{removed['id']}"
                if old != f"{v['provider']}:{removed['name']}":
                    _remove_from_openclaw(old)
            return True
    return False


def delete_vendor(vendor_id: str) -> bool:
    data = _load_data()
    for i, v in enumerate(data["vendors"]):
        if v["id"] == vendor_id:
            # Remove all keys from OpenClaw first
            for key in v.get("keys", []):
                ocp_key = f"{v['provider']}@{key['name']}"
                _remove_from_openclaw(ocp_key)
                old_key = f"{v['provider']}-{key['id']}"
                if old_key != ocp_key:
                    _remove_from_openclaw(old_key)
            # Remove the aggregate entry if exists
            _remove_from_openclaw(v["provider"])
            # Remove from vendors list
            data["vendors"].pop(i)
            _save_data(data)
            return True
    return False


# ── OpenClaw Sync ────────────────────────────────────────

def _ocp_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if not any(url.endswith(f"/v{i}") for i in range(1, 5)):
        url += "/v1"
    return url


def _sync_key_to_openclaw(vendor: dict, key_entry: dict, models_override: Optional[list[str]] = None) -> None:
    ocp_key = f"{vendor['provider']}@{key_entry['name']}"
    old_key = f"{vendor['provider']}-{key_entry['id']}"
    cfg = _load_openclaw_config()
    ocp_base_url = _ocp_url(vendor["api_url"])

    if "models" not in cfg:
        cfg["models"] = {}
    if "providers" not in cfg["models"]:
        cfg["models"]["providers"] = {}

    # Remove old key-format entry
    old_prov = cfg["models"]["providers"].pop(old_key, None)

    models = models_override if models_override is not None else key_entry.get("models", [])
    models_obj = [{"id": m, "name": m} for m in models] if models and isinstance(models[0], str) else models

    # Write key-level entry for the provider:key combo
    provider_entry = {
        "apiKey": key_entry["api_key"],
        "baseUrl": ocp_base_url,
        "models": models_obj,
    }
    cfg["models"]["providers"][ocp_key] = provider_entry

    # Aggregate models under the bare provider name (only from per-key entries)
    # NOTE: Aggregate entry has NO apiKey — OpenClaw reads the key from per-key entries
    provider_name = vendor["provider"]
    all_models = {}
    agg_base_url = ocp_base_url
    for pkey, pval in cfg["models"]["providers"].items():
        # Only aggregate from per-key entries (e.g. "xiaomi-token-plan:暗"), not the aggregate itself
        if "@" in pkey and pkey.split("@")[0] == provider_name:
            for m in pval.get("models", []):
                mid = m["id"] if isinstance(m, dict) else m
                if mid not in all_models:
                    all_models[mid] = m
            if not agg_base_url and pval.get("baseUrl"):
                agg_base_url = pval["baseUrl"]
    cfg["models"]["providers"][provider_name] = {
        "baseUrl": agg_base_url,
        "models": list(all_models.values()),
    }

    # Auth profiles in openclaw.json
    if "auth" not in cfg:
        cfg["auth"] = {}
    if "profiles" not in cfg["auth"]:
        cfg["auth"]["profiles"] = {}

    cfg["auth"]["profiles"].pop(old_key, None)
    if ocp_key not in cfg["auth"]["profiles"]:
        cfg["auth"]["profiles"][ocp_key] = {
            "provider": provider_name,
            "mode": "api_key",
        }

    if "order" not in cfg["auth"]:
        cfg["auth"]["order"] = {}

    for pn, keys in list(cfg["auth"]["order"].items()):
        if old_key in keys:
            keys.remove(old_key)
            break

    if provider_name not in cfg["auth"]["order"]:
        cfg["auth"]["order"][provider_name] = []

    existing = cfg["auth"]["order"][provider_name]
    if ocp_key not in existing:
        existing.append(ocp_key)

    _save_openclaw_config(cfg)

    # ── Update agent auth-profiles.json ──
    try:
        auth_data = _load_auth_profiles()
        auth_data.setdefault("profiles", {})
        auth_data["profiles"].pop(old_key, None)
        auth_data["profiles"][ocp_key] = {
            "type": "api_key",
            "provider": provider_name,
            "key": key_entry["api_key"],
        }
        _save_auth_profiles(auth_data)
    except Exception:
        pass

    # ── Update agent models.json ──
    try:
        mdata = _load_agent_models()
        mdata.setdefault("providers", {})
        # Per-key provider entry
        mdata["providers"][ocp_key] = {
            "baseUrl": ocp_base_url,
            "apiKey": key_entry["api_key"],
            "models": models_obj,
        }
        # Aggregated provider entry (rebuild from per-key entries only)
        agg_models = {}
        agg_base_url = ocp_base_url
        for pk, pv in mdata["providers"].items():
            if "@" in pk and pk.split("@")[0] == provider_name:
                for m in pv.get("models", []):
                    mid = m["id"] if isinstance(m, dict) else m
                    if mid not in agg_models:
                        agg_models[mid] = m if isinstance(m, dict) else {"id": m, "name": m}
                if pv.get("baseUrl"):
                    agg_base_url = pv["baseUrl"]
        mdata["providers"][provider_name] = {
            "baseUrl": agg_base_url,
            "api": "openai-completions",
            "models": list(agg_models.values()),
        }
        _save_agent_models(mdata)
    except Exception:
        pass

    # ── Update agents.defaults.models (controls which models appear in web UI) ──
    try:
        defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
        defaults_models = defaults.setdefault("models", {})
        # Add models from this key
        for m in models_obj:
            mid = m["id"] if isinstance(m, dict) else m
            model_ref = f"{provider_name}/{mid}"
            if model_ref not in defaults_models:
                defaults_models[model_ref] = {}
        _save_openclaw_config(cfg)
    except Exception:
        pass


def _remove_from_openclaw(ocp_key: str) -> None:
    cfg = _load_openclaw_config()

    providers = cfg.get("models", {}).get("providers", {})
    if ocp_key in providers:
        del providers[ocp_key]

    profiles = cfg.get("auth", {}).get("profiles", {})
    if ocp_key in profiles:
        del profiles[ocp_key]

    order = cfg.get("auth", {}).get("order", {})
    for provider_name, keys in order.items():
        if ocp_key in keys:
            keys.remove(ocp_key)
            break

    _save_openclaw_config(cfg)

    # Clean agent auth-profiles.json
    auth_data = _load_auth_profiles()
    if ocp_key in auth_data.get("profiles", {}):
        del auth_data["profiles"][ocp_key]
        _save_auth_profiles(auth_data)

    # Clean agent models.json
    mdata = _load_agent_models()
    if ocp_key in mdata.get("providers", {}):
        del mdata["providers"][ocp_key]
        _save_agent_models(mdata)


def reconcile_openclaw() -> None:
    """Remove any OpenClaw entries that don't correspond to a current enabled key."""
    cfg = _load_openclaw_config()
    vendors = get_vendors()

    expected_key_ids = set()
    expected_providers = set()
    for v in vendors:
        for k in v.get("keys", []):
            if k.get("enabled", True):
                expected_key_ids.add(f"{v['provider']}@{k['name']}")
                expected_providers.add(v["provider"])

    providers = cfg.get("models", {}).get("providers", {})
    profiles = cfg.get("auth", {}).get("profiles", {})
    order = cfg.get("auth", {}).get("order", {})

    changed = False
    # Remove stale key-level entries from models.providers
    for ocp_key in list(providers.keys()):
        if "@" not in ocp_key:
            continue
        if ocp_key not in expected_key_ids:
            del providers[ocp_key]
            profiles.pop(ocp_key, None)
            changed = True
        else:
            if "models" not in providers[ocp_key]:
                providers[ocp_key]["models"] = []
                changed = True
            else:
                existing = providers[ocp_key]["models"]
                if existing and isinstance(existing[0], str):
                    providers[ocp_key]["models"] = [{"id": m, "name": m} for m in existing]
                    changed = True
                elif existing and isinstance(existing[0], dict) and "id" not in existing[0] and "name" in existing[0]:
                    providers[ocp_key]["models"] = [{"id": m["name"], "name": m["name"]} for m in existing]
                    changed = True

    # Remove stale profiles
    for ocp_key in list(profiles.keys()):
        if ocp_key not in expected_key_ids and ocp_key not in providers:
            del profiles[ocp_key]
            changed = True

    # Clean order to only reference expected keys
    for provider_name in list(order.keys()):
        before = len(order[provider_name])
        order[provider_name] = [k for k in order[provider_name] if k in expected_key_ids]
        if len(order[provider_name]) != before:
            changed = True
        if not order[provider_name]:
            del order[provider_name]
            changed = True

    # Remove aggregate entries for providers with no enabled keys
    for ocp_key in list(providers.keys()):
        if "@" not in ocp_key:
            pname = ocp_key
            has_enabled_key = any(
                k.split("@")[0] == pname for k in providers if "@" in k
            )
            if not has_enabled_key:
                del providers[ocp_key]
                profiles.pop(ocp_key, None)
                changed = True

    # Re-aggregate provider-level model entries (no apiKey — per-key entries hold the key)
    provider_model_names = set()
    for ocp_key, entry in list(providers.items()):
        pname = ocp_key.split("@")[0]
        if "@" in ocp_key and pname:
            provider_model_names.add(pname)
    for pname in provider_model_names:
        all_models = {}
        base_url = None
        for ocp_key, entry in providers.items():
            if ocp_key.split("@")[0] == pname:
                for m in entry.get("models", []):
                    mid = m["id"] if isinstance(m, dict) else m
                    if mid not in all_models:
                        all_models[mid] = m
                if not base_url:
                    base_url = entry.get("baseUrl", "")
        if pname in providers:
            old = providers[pname]
            new_models = list(all_models.values())
            # Remove apiKey from aggregate entry — OpenClaw reads key from per-key entries
            if "apiKey" in old:
                del old["apiKey"]
                changed = True
            if old.get("models") != new_models:
                old["models"] = new_models
                changed = True
            if base_url and old.get("baseUrl") != base_url:
                old["baseUrl"] = base_url
                changed = True

    if changed:
        _save_openclaw_config(cfg)

    # ── Reconcile agents.defaults.models (aliases) ──
    defaults_models = cfg.get("agents", {}).get("defaults", {}).get("models", {})
    if defaults_models:
        model_changed = False
        for model_ref in list(defaults_models.keys()):
            provider_name = model_ref.split("/")[0] if "/" in model_ref else model_ref
            if provider_name not in expected_providers:
                del defaults_models[model_ref]
                model_changed = True
        if model_changed:
            _save_openclaw_config(cfg)

    # ── Reconcile agent auth-profiles.json ──
    try:
        auth_data = _load_auth_profiles()
        a_changed = False
        for ocp_key in list(auth_data.get("profiles", {}).keys()):
            if ocp_key not in expected_key_ids:
                del auth_data["profiles"][ocp_key]
                a_changed = True
        if a_changed:
            _save_auth_profiles(auth_data)
    except Exception:
        pass

    # ── Reconcile agent models.json ──
    try:
        mdata = _load_agent_models()
        m_changed = False
        allowed_models = set(expected_key_ids) | expected_providers
        for ocp_key in list(mdata.get("providers", {}).keys()):
            if ocp_key not in allowed_models:
                del mdata["providers"][ocp_key]
                m_changed = True
        # Rebuild aggregate entries from per-key entries
        agg_providers = set()
        for pk in list(mdata.get("providers", {}).keys()):
            if "@" in pk:
                agg_providers.add(pk.split("@")[0])
        for pname in agg_providers:
            agg_models = {}
            agg_base_url = ""
            for pk, pv in mdata.get("providers", {}).items():
                if "@" in pk and pk.split("@")[0] == pname:
                    for m in pv.get("models", []):
                        mid = m["id"] if isinstance(m, dict) else m
                        if mid not in agg_models:
                            agg_models[mid] = m if isinstance(m, dict) else {"id": m, "name": m}
                    if pv.get("baseUrl"):
                        agg_base_url = pv["baseUrl"]
            mdata["providers"][pname] = {
                "baseUrl": agg_base_url,
                "api": "openai-completions",
                "models": list(agg_models.values()),
            }
            m_changed = True
        if m_changed:
            _save_agent_models(mdata)
    except Exception:
        pass


def _collect_key_references(cfg: dict) -> list[tuple[str, str, str]]:
    seen = set()
    refs = []

    profiles = cfg.get("auth", {}).get("profiles", {})
    order = cfg.get("auth", {}).get("order", {})
    providers = cfg.get("models", {}).get("providers", {})

    for ocp_key, auth_profile in profiles.items():
        provider_name = auth_profile.get("provider", "")
        provider_cfg = providers.get(provider_name, {})
        base_url = provider_cfg.get("baseUrl", "")
        api_key_val = provider_cfg.get("apiKey", "")
        if provider_name and api_key_val and ocp_key not in seen:
            seen.add(ocp_key)
            refs.append((ocp_key, provider_name, api_key_val, base_url))

    for provider_name, keys in order.items():
        provider_cfg = providers.get(provider_name, {})
        base_url = provider_cfg.get("baseUrl", "")
        api_key_val = provider_cfg.get("apiKey", "")
        for ocp_key in keys:
            if ocp_key in seen:
                continue
            if not base_url and not api_key_val:
                parts = ocp_key.split("@", 1)
                if len(parts) == 2:
                    sub_provider = parts[0]
                    sub_cfg = providers.get(sub_provider, {})
                    base_url = sub_cfg.get("baseUrl", "")
                    api_key_val = sub_cfg.get("apiKey", "")
            if api_key_val and ocp_key not in seen:
                seen.add(ocp_key)
                refs.append((ocp_key, provider_name, api_key_val, base_url))

    return refs


def sync_from_openclaw() -> dict:
    if not OPENCLAW_CONFIG_PATH.exists():
        return {"synced": 0, "total": 0}

    cfg = _load_openclaw_config()
    data = _load_data()
    refs = _collect_key_references(cfg)
    added_keys = 0

    for ocp_key, provider_name, api_key_val, base_url in refs:
        vendor = None
        for v in data["vendors"]:
            if v["provider"] == provider_name and v["api_url"] == base_url.rstrip("/"):
                vendor = v
                break

        if not vendor:
            vendor = {
                "id": _next_id(data.get("vendors", [])),
                "name": provider_name.replace("-", " ").title(),
                "provider": provider_name,
                "api_url": base_url.rstrip("/"),
                "keys": [],
            }
            data["vendors"].append(vendor)

        key_name = ocp_key.split("@")[-1] if "@" in ocp_key else ocp_key.split("-")[-1]

        found = False
        for k in vendor.get("keys", []):
            if k["name"] == key_name or k["api_key"] == api_key_val:
                found = True
                break
        if found:
            continue

        entry = {
            "id": _next_id(vendor.get("keys", [])),
            "name": key_name,
            "api_key": api_key_val,
            "enabled": True,
        }
        vendor["keys"].append(entry)
        added_keys += 1

    _save_data(data)
    total = sum(len(v.get("keys", [])) for v in data.get("vendors", []))
    return {"synced": added_keys, "total": total}


# ── Settings ─────────────────────────────────────────────

def get_settings() -> dict:
    return _load_data().get("settings", {"check_interval_seconds": 300})


def update_settings(**kwargs) -> dict:
    data = _load_data()
    if "settings" not in data:
        data["settings"] = {"check_interval_seconds": 300}
    for key in ("check_interval_seconds",):
        if key in kwargs:
            val = kwargs[key]
            if isinstance(val, (int, float)) and val >= 10:
                data["settings"][key] = int(val)
    if "gateway" in kwargs:
        data["settings"]["gateway"] = kwargs["gateway"]
    _save_data(data)
    return data["settings"]


# ── Gateway ──────────────────────────────────────────────

MANAGER_VERSION = "1.0.0"
MIN_OPENCLAW_VERSION = "2026.3.0"
RECOMMENDED_OPENCLAW_VERSION = "2026.6.11"


def get_openclaw_version() -> str:
    try:
        r = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def restart_gateway() -> dict:
    result = {"success": False, "message": ""}
    try:
        r = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            result["success"] = True
            result["message"] = r.stdout.strip()
        else:
            result["message"] = r.stderr.strip() or r.stdout.strip()
            r2 = subprocess.run(
                ["openclaw", "doctor", "--fix"],
                capture_output=True, text=True, timeout=30,
            )
            result["fallback_message"] = r2.stdout.strip()
            if r2.returncode == 0:
                result["success"] = True
    except FileNotFoundError:
        result["message"] = "openclaw command not found"
    except subprocess.TimeoutExpired:
        result["message"] = "Gateway restart timed out"
    except Exception as e:
        result["message"] = str(e)
    return result


def get_gateway_status() -> dict:
    result = {"running": False, "port": None, "message": ""}
    try:
        r = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            result["running"] = True
            result["message"] = r.stdout.strip()
            for line in r.stdout.splitlines():
                if "port" in line.lower():
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.isdigit() and 1000 < int(p) < 100000:
                            result["port"] = int(p)
                            break
        else:
            result["message"] = r.stderr.strip() or r.stdout.strip()
    except FileNotFoundError:
        result["message"] = "openclaw command not found"
    except Exception as e:
        result["message"] = str(e)
    return result
