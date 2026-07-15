import os

# 必须在导入 app.utils.config 之前设置：get_settings() 带 lru_cache，
# 且 app.database.db 在模块导入期就会建 engine，晚一步就来不及覆盖。
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
