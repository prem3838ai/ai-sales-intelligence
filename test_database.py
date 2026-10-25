import pandas as pd
from src.database import import_csv_to_sqlite, query_sales

def test_sqlite_import_and_query(tmp_path):
    csv_path = tmp_path / "sales.csv"
    db_path = tmp_path / "sales.db"
    pd.DataFrame({
        "order_id": ["O1", "O2"],
        "order_date": ["2025-01-01", "2025-01-02"],
        "customer_id": ["C1", "C2"],
        "product": ["Mouse", "Bottle"],
        "category": ["Electronics", "Home"],
        "quantity": [2, 1],
        "unit_price": [10.0, 15.0],
        "unit_cost": [4.0, 5.0],
    }).to_csv(csv_path, index=False)
    assert import_csv_to_sqlite(csv_path, db_path) == 2
    result = query_sales(db_path)
    assert len(result) == 2
    assert result["revenue"].sum() == 35.0
