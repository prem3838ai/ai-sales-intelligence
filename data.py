from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "sales.csv"
REQUIRED_COLUMNS = {
    "order_id", "order_date", "customer_id", "product", "category",
    "quantity", "unit_price", "unit_cost"
}

def load_sales_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load transaction-level sales data and derive revenue/profit columns."""
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Run `python scripts/generate_sample_data.py`."
        )
    df = pd.read_csv(path, parse_dates=["order_date"])
    validate_sales_data(df)
    df["revenue"] = df["quantity"] * df["unit_price"]
    df["profit"] = df["quantity"] * (df["unit_price"] - df["unit_cost"])
    return df

def validate_sales_data(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if df.empty:
        raise ValueError("Sales dataset is empty.")
    if df[list(REQUIRED_COLUMNS)].isnull().any().any():
        raise ValueError("Required columns contain missing values.")
    if (df["quantity"] <= 0).any():
        raise ValueError("Quantity must be greater than zero.")
    if (df["unit_price"] < 0).any() or (df["unit_cost"] < 0).any():
        raise ValueError("Price and cost cannot be negative.")
