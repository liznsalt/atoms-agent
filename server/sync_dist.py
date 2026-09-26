# 临时：同步 client/dist -> server/client_dist（部署包内嵌前端，用后可留作部署工具）
import shutil
from pathlib import Path

SRC = Path(r"d:\项目\atoms-agent\client\dist")
DST = Path(r"d:\项目\atoms-agent\server\client_dist")

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
files = list(DST.rglob("*"))
print(f"synced {len([f for f in files if f.is_file()])} files -> {DST}")
