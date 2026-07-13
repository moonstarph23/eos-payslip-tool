import base64
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TAURI_CONFIG = ROOT / "src-tauri" / "tauri.conf.json"


def _config():
    return json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))


def test_updater_public_key_is_a_tauri_minisign_key_box():
    encoded_key = _config()["tauri"]["updater"]["pubkey"]
    key_box = base64.b64decode(encoded_key, validate=True).decode("utf-8")
    lines = key_box.splitlines()

    assert lines[0].startswith("untrusted comment: minisign public key:")
    assert len(base64.b64decode(lines[1], validate=True)) == 42


def test_all_configured_bundle_icons_exist():
    for relative_path in _config()["tauri"]["bundle"]["icon"]:
        assert (ROOT / "src-tauri" / relative_path).is_file(), relative_path
