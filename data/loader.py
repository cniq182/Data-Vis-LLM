"""CSV ingestion and schema extraction.

Only the object returned by `DatasetSchema.to_prompt_dict()` is ever sent to
the LLM: column names, dtypes, simple statistics and a few sample rows.
"""
from __future__ import annotations

import csv
import io
import json
import re
import warnings
from dataclasses import asdict, dataclass

import pandas as pd

SAMPLE_ROWS = 3
MAX_SAMPLE_CHARS = 40          # truncate long strings in sample rows
DATE_PARSE_THRESHOLD = 0.9     # share of values that must parse as dates
ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")


class DataLoadError(Exception):
    """Raised when a CSV cannot be turned into a usable DataFrame."""


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    dtype: str           # pandas dtype, e.g. "float64"
    vl_type: str         # Vega-Lite type: quantitative | temporal | nominal
    n_unique: int
    n_missing: int


@dataclass(frozen=True)
class DatasetSchema:
    n_rows: int
    columns: list[ColumnInfo]
    sample: list[dict[str, object]]

    @property
    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            "n_rows": self.n_rows,
            "columns": [asdict(c) for c in self.columns],
            "sample_rows": self.sample,
        }


def load_csv(raw: bytes) -> pd.DataFrame:
    """Read CSV bytes, trying common encodings and sniffing the delimiter."""
    if not raw.strip():
        raise DataLoadError("The file is empty.")
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(
                io.BytesIO(raw), sep=None, engine="python", encoding=encoding
            )
            break
        except UnicodeDecodeError as exc:
            last_error = exc
        except (pd.errors.ParserError, pd.errors.EmptyDataError, csv.Error) as exc:
            raise DataLoadError(f"Could not parse CSV: {exc}") from exc
    else:
        raise DataLoadError(f"Unsupported text encoding: {last_error}")

    if df.empty or df.shape[1] == 0:
        raise DataLoadError("The CSV has no rows or no columns.")

    df.columns = _clean_column_names(df.columns)
    return _parse_dates(df)


def _clean_column_names(columns: pd.Index) -> list[str]:
    """Make names safe for Vega-Lite and unique.

    Vega-Lite interprets '.' and '[]' in field names as nested access,
    so 'price.usd' would silently resolve to nothing.
    """
    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for i, col in enumerate(columns):
        name = re.sub(r"[.\[\]\\]", "_", str(col)).strip() or f"column_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        cleaned.append(name)
    return cleaned


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert text columns to datetime when almost all values parse."""
    for col in df.select_dtypes(include=["object", "string"]).columns:
        values = df[col].dropna()
        if values.empty:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
        if parsed.notna().sum() >= DATE_PARSE_THRESHOLD * len(values):
            df[col] = parsed
    return df


def _vl_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "nominal"
    if pd.api.types.is_numeric_dtype(series):
        return "quantitative"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "temporal"
    return "nominal"


def _truncate(value: object) -> object:
    if isinstance(value, str) and len(value) > MAX_SAMPLE_CHARS:
        return value[:MAX_SAMPLE_CHARS] + "..."
    return value


def extract_schema(df: pd.DataFrame) -> DatasetSchema:
    columns = [
        ColumnInfo(
            name=str(col),
            dtype=str(df[col].dtype),
            vl_type=_vl_type(df[col]),
            n_unique=int(df[col].nunique()),
            n_missing=int(df[col].isna().sum()),
        )
        for col in df.columns
    ]
    records = json.loads(
        df.head(SAMPLE_ROWS).to_json(orient="records", date_format="iso")
    )
    sample = [{k: _truncate(v) for k, v in row.items()} for row in records]
    return DatasetSchema(n_rows=len(df), columns=columns, sample=sample)
