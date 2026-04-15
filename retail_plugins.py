import pandas as pd
import os

class FMCGSmartPlugin:
    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cycle_data_path = os.path.join(base_dir, "output", "cycle_time_results.csv")
        self.mba_data_path = os.path.join(base_dir, "output", "mba_results.csv")
        
        if os.path.exists(self.cycle_data_path):
            self.cycle_data = pd.read_csv(self.cycle_data_path)
        else:
            self.cycle_data = pd.DataFrame()
            
        if os.path.exists(self.mba_data_path):
            self.mba_data = pd.read_csv(self.mba_data_path)
        else:
            self.mba_data = pd.DataFrame()

    def get_replenishment_suggestions(self, store_id: str) -> str:
        if self.cycle_data.empty:
            return "Không có dữ liệu phân tích cycle_time."
            
        # Lọc các sản phẩm có chu kỳ ngắn (T_cycle thấp)
        top_products = self.cycle_data[self.cycle_data['store_id'] == store_id].sort_values(by='T_cycle').head(3)
        
        # 'product_id' đã được đổi tên thành 'product_code'
        if 'product_code' in top_products.columns:
            res = top_products[['product_code', 'T_cycle']].to_dict(orient='records')
        else:
            res = top_products[['product_id', 'T_cycle']].to_dict(orient='records')
            
        return f"Dựa trên lịch sử, các sản phẩm này sắp đến kỳ mua lại: {res}"

    def get_upsell_suggestions(self, product_code: str) -> str:
        if self.mba_data.empty:
            return "Không có dữ liệu phân tích MBA."
            
        # Tra cứu từ mba_results.csv
        recommendations = self.mba_data[self.mba_data['product_a'] == product_code].sort_values(by='lift', ascending=False).head(2)
        if recommendations.empty:
            return "Không có gợi ý mua kèm cho sản phẩm này."
        
        items = recommendations['product_b'].tolist()
        return f"Khách mua {product_code} thường mua thêm: {', '.join(items)}"