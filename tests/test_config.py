import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import json

import deft_pro.config as config


def test_fresh_config_has_all_buttons():
    data = config.fresh_config()
    bindings = data["profiles"]["Default"]["bindings"]
    assert set(bindings) == {str(n) for n, _ in config.BUTTONS}
    assert all(value == {"type": "passthrough"} for value in bindings.values())


def test_load_config_repairs_missing_fields(tmp_path, monkeypatch):
    app_dir = tmp_path / "deft-pro"
    cfg = app_dir / "config.json"
    monkeypatch.setattr(config, "APP_DIR", app_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"profiles": {"My Profile": {"bindings": {"10": {"type": "disabled"}}}}}))

    loaded = config.load_config()
    bindings = loaded["profiles"]["My Profile"]["bindings"]
    assert loaded["active_profile"] == "My Profile"
    assert bindings["10"] == {"type": "disabled"}
    assert bindings["1"] == {"type": "passthrough"}


def test_deft_pro_udev_rule_handles_existing_devices():
    from pathlib import Path

    rule = Path(__file__).parents[1] / "packaging" / "deb" / "etc" / "udev" / "rules.d" / "70-deft-pro-configurator.rules"
    text = rule.read_text(encoding="utf-8")
    assert not any(line.strip() and not line.lstrip().startswith('#') and 'ACTION=="add"' in line for line in text.splitlines())
    assert 'ATTRS{name}=="*DEFT Pro*"' in text
    assert 'TAG+="uaccess"' in text
