import os

# 必须在导入 app.utils.config 之前设置：get_settings() 带 lru_cache，
# 且 app.database.db 在模块导入期就会建 engine，晚一步就来不及覆盖。
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# 强制置空而非 setdefault：OpenAIClient 在 import 期就按这个值决定建不建
# client，留着 .env 里的真 key 会让测试真的打 OpenAI 接口。load_dotenv
# 默认不覆盖已存在的环境变量，所以这里能压住 .env。
os.environ["OPENAI_API_KEY"] = ""
