import json
from pathlib import Path

import pandas as pd

from exchange.market_data import REQUIRED_CANDLE_COLUMNS


# Compatibility alias; the canonical candle contract belongs to market data.
REQUIRED_COLUMNS = REQUIRED_CANDLE_COLUMNS


class FrozenMarketDataStore:
    """CSV-backed storage for immutable, reproducible candle snapshots."""

    def __init__(self, root="data/snapshots"):
        self.root = Path(root)

    def _paths(self, name):
        if not name or Path(name).name != name:
            raise ValueError("Snapshot name must be a simple file name")
        return self.root / f"{name}.csv", self.root / f"{name}.json"

    def save(self, name, candles, metadata=None, overwrite=False):
        csv_path, metadata_path = self._paths(name)
        if (csv_path.exists() or metadata_path.exists()) and not overwrite:
            raise FileExistsError(f"Snapshot already exists: {name}")

        missing = set(REQUIRED_COLUMNS) - set(candles.columns)
        if missing:
            raise ValueError(f"Missing candle columns: {sorted(missing)}")

        self.root.mkdir(parents=True, exist_ok=True)
        normalized = candles.copy().sort_values("open_time").reset_index(drop=True)
        normalized.to_csv(csv_path, index=False)

        details = {
            "name": name,
            "rows": len(normalized),
            "first_open_time": str(normalized["open_time"].iloc[0]),
            "last_open_time": str(normalized["open_time"].iloc[-1]),
            **(metadata or {}),
        }
        metadata_path.write_text(
            json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return csv_path

    def load(self, name):
        csv_path, _ = self._paths(name)
        if not csv_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {name}")

        df = pd.read_csv(csv_path)
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
        return df.sort_values("open_time").reset_index(drop=True)

    def metadata(self, name):
        _, metadata_path = self._paths(name)
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def save_bundle(self, name, symbol, snapshots, overwrite=False):
        """Persist a small manifest that composes immutable single-TF snapshots."""
        if not name or Path(name).name != name:
            raise ValueError("Bundle name must be a simple file name")
        path = self.root / f"{name}.bundle.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Snapshot bundle already exists: {name}")
        if not snapshots:
            raise ValueError("At least one timeframe snapshot is required")
        for timeframe, snapshot in snapshots.items():
            metadata = self.metadata(snapshot)
            if metadata.get("symbol", symbol).upper() != symbol.upper():
                raise ValueError(f"Snapshot {snapshot} belongs to a different symbol")
            declared = metadata.get("timeframe")
            if declared and declared != timeframe:
                raise ValueError(f"Snapshot {snapshot} timeframe mismatch")
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "name": name, "symbol": symbol.upper(), "snapshots": snapshots,
        }, indent=2), encoding="utf-8")
        return path

    def load_bundle(self, name):
        from exchange.multi_timeframe import MultiTimeframeMarketData

        if not name or Path(name).name != name:
            raise ValueError("Bundle name must be a simple file name")
        path = self.root / f"{name}.bundle.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        frames = {tf: self.load(snapshot) for tf, snapshot in payload["snapshots"].items()}
        return MultiTimeframeMarketData(payload["symbol"], frames)
