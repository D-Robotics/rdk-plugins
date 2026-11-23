import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

market = json.loads(Path("marketplace.json").read_text(encoding="utf-8"))
plugin = next(item for item in market["plugins"] if item["name"] == "rdk-camera-workshop")
archive = Path("dist") / f'{plugin["name"]}-{plugin["version"]}.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == plugin["source"]["sha256"]
with ZipFile(archive) as z:
    assert z.testzip() is None
    prefix = plugin["name"] + "/"
    manifest = json.loads(z.read(prefix + "SOURCE-MANIFEST.json"))
    assert manifest["version"] == plugin["version"]
    assert sorted(z.namelist()) == sorted(prefix + name for name in ["SOURCE-MANIFEST.json", *(row["path"] for row in manifest["files"])])
    for row in manifest["files"]:
        data = z.read(prefix + row["path"])
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
    z.extractall(Path(os.environ["RUNNER_TEMP"]) / "Camera AI 课堂")
