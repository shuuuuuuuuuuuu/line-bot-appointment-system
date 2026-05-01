from database import SessionLocal
import models

def seed_services():
    db = SessionLocal()
    
    initial_services = [
        {"service_name": "感情與人際的糾葛"},
        {"service_name": "工作與人生方向"},
        {"service_name": "靈魂使命與學習課題"},
        {"service_name": "天賦潛能與靈魂藍圖"},
        {"service_name": "身體疾病的根源"},
        {"service_name": "深層創傷與能量卡點"},
        {"service_name": "前世今生的業力關聯"},
        {"service_name": "已逝親人或寵物的訊息"},
        {"service_name": "祖源與原生家庭能量牽連"},
        {"service_name": "晶礦、動物等意識連結"},
        {"service_name": "頌缽療癒"},
    ]

    try:
        for item in initial_services:
            
            exists = db.query(models.Service).filter(models.Service.service_name == item["service_name"]).first()
            
            if not exists:
                new_service = models.Service(
                    service_name=item["service_name"]
                )
                db.add(new_service)
        
        db.commit()
        print("資料初始化成功！")
    except Exception as e:
        db.rollback()
        print(f"初始化失敗: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_services()