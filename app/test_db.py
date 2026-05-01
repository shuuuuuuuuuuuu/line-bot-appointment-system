# test_db.py
from database import engine
from models import Base, Client, Service, Appointment, AppointmentItem 
# 重點：必須 import 具體的 class，Base 才會知道要建哪些表

def force_create():
    print("正在連線至資料庫並嘗試建立資料表...")
    try:
        # 這會建立所有繼承 Base 的類別所對應的表
        Base.metadata.create_all(bind=engine)
        print("---")
        print("執行完成！請至 MySQL 輸入 'show tables;' 檢查。")
        print("提醒：你的表名應該是 'services' (複數) 而非 'service'。")
    except Exception as e:
        print(f"建立失敗！錯誤訊息：{e}")

if __name__ == "__main__":
    force_create()