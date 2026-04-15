"""
stockout_analysis.py
====================
Xử lý lịch sử đơn hàng để tính toán các chỉ số:
  1. T_cycle (Cycle Time) - Thời gian trung bình giữa các lần nhập hàng/đặt hàng.
  2. MBA (Market Basket Analysis) - Mối liên hệ giữa các sản phẩm (Support, Confidence, Lift).
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
import itertools
from collections import Counter

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════

DATA_PATH = Path(__file__).parent / "data" / "order_history.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Đọc CSV và parse ngày."""
    df = pd.read_csv(path, parse_dates=["order_date"])
    print(f"📦  Loaded {len(df):,} orders  |  "
          f"Stores: {df['store_id'].nunique()}  |  "
          f"Products: {df['product_code'].nunique()}")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# 2. T_CYCLE CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_cycle_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính T_cycle cho mỗi cặp (store_id, product_code):
    T_cycle = Khoảng cách trung bình (ngày) giữa 2 đơn hàng liên tiếp.
    """
    # Sắp xếp theo thơi gian
    df_sorted = df.sort_values(["store_id", "product_code", "order_date"])
    
    # Tính hiệu số ngày giữa các đơn hàng liên tiếp
    df_sorted["prev_date"] = df_sorted.groupby(["store_id", "product_code"])["order_date"].shift(1)
    df_sorted["days_diff"] = (df_sorted["order_date"] - df_sorted["prev_date"]).dt.days
    
    # Gom nhóm tính trung bình days_diff
    agg = df_sorted.groupby(["store_id", "product_code", "uom_code"]).agg(
        T_cycle=("days_diff", "mean"),
        total_orders=("order_id", "count"),
        total_qty=("quantity", "sum")
    ).reset_index()
    
    # Làm tròn
    agg["T_cycle"] = agg["T_cycle"].round(2)
    
    return agg

# ══════════════════════════════════════════════════════════════════════════════
# 3. MARKET BASKET ANALYSIS (MBA)
# ══════════════════════════════════════════════════════════════════════════════

def perform_mba(df: pd.DataFrame, min_support: float = 0.001) -> pd.DataFrame:
    """
    Phân tích giỏ hàng. 
    Vì trong data giả lập order_id độc bản, ta sẽ thử gom nhóm theo (store_id, order_date)
    để tìm các sản phẩm thường được bán cùng nhau tại 1 cửa hàng trong cùng 1 ngày.
    """
    # Gom nhóm thành 'baskets' theo (store_id, order_date)
    # Nếu data của bạn có transaction_id thực sự, hãy đổi 'store_id', 'order_date' thành 'transaction_id'
    baskets = df.groupby(["store_id", "order_date"])["product_code"].apply(list)
    total_baskets = len(baskets)
    
    if total_baskets == 0:
        return pd.DataFrame()

    # Đếm số lần xuất hiện đơn lẻ (trong mỗi basket)
    item_counts = Counter(itertools.chain.from_iterable(baskets.map(set)))
    
    # Đếm số lần các cặp (A, B) xuất hiện cùng nhau
    pair_counts = Counter()
    for basket in baskets:
        unique_items = sorted(list(set(basket)))
        if len(unique_items) < 2:
            continue
        for pair in itertools.combinations(unique_items, 2):
            pair_counts[pair] += 1
            
    uom_mapping = df.drop_duplicates("product_code").set_index("product_code")["uom_code"].to_dict() if "uom_code" in df.columns else {}
    
    # Tính toán chỉ số
    mba_data = []
    for (item_a, item_b), count in pair_counts.items():
        support_ab = count / total_baskets
        if support_ab < min_support:
            continue
            
        support_a = item_counts[item_a] / total_baskets
        support_b = item_counts[item_b] / total_baskets
        
        # Confidence A -> B: P(B|A)
        confidence_a_b = support_ab / support_a
        # Confidence B -> A: P(A|B)
        confidence_b_a = support_ab / support_b
        
        # Lift: P(A,B) / (P(A)*P(B))
        lift = support_ab / (support_a * support_b)
        
        mba_data.append({
            "product_a": item_a,
            "uom_a": uom_mapping.get(item_a, ""),
            "product_b": item_b,
            "uom_b": uom_mapping.get(item_b, ""),
            "support": round(support_ab, 4),
            "conf_A_to_B": round(confidence_a_b, 3),
            "conf_B_to_A": round(confidence_b_a, 3),
            "lift": round(lift, 2)
        })
        
    mba_df = pd.DataFrame(mba_data)
    if not mba_df.empty:
        mba_df = mba_df.sort_values("lift", ascending=False)
    return mba_df

# ══════════════════════════════════════════════════════════════════════════════
# 4. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── Load ──
    df = load_data()

    # ── T-Cycle ──
    print("\n" + "═" * 60)
    print("  ⭐  T-CYCLE CALCULATION (By Store & Product)")
    print("═" * 60)
    cycle_stats = calculate_cycle_time(df)
    print(cycle_stats.head(15).to_string(index=False))
    
    cycle_path = OUTPUT_DIR / "cycle_time_results.csv"
    cycle_stats.to_csv(cycle_path, index=False)
    print(f"\n💾  Cycle Time Results → {cycle_path}")

    # ── Market Basket Analysis ──
    print("\n" + "═" * 60)
    print("  🛒  MARKET BASKET ANALYSIS (Top Associations)")
    print("═" * 60)
    
    # Thử min_support thấp vì data có thể phân mảnh
    mba_results = perform_mba(df, min_support=0.0001)
    
    if not mba_results.empty:
        print(mba_results.head(15).to_string(index=False))
        mba_path = OUTPUT_DIR / "mba_results.csv"
        mba_results.to_csv(mba_path, index=False)
        print(f"\n💾  MBA Results → {mba_path}")
    else:
        print("  (Không tìm thấy cặp sản phẩm nào có quan hệ đủ lớn trong cùng Store/Ngày)")

if __name__ == "__main__":
    main()
