# 邮件配置
import os
from dotenv import load_dotenv

# 尝试加载.env文件中的环境变量
load_dotenv()

MAIL_CONFIG = {
    "SMTP_SERVER": os.getenv("SMTP_SERVER", "smtp.qq.com"),  # SMTP服务器地址
    "SMTP_PORT": int(os.getenv("SMTP_PORT", "587")),  # SMTP端口
    "SMTP_USER": os.getenv("SMTP_USER", "739238103@qq.com"),  # SMTP用户名
    "SMTP_PASS": os.getenv("SMTP_PASS", "bhlhpflfrzxobcjj"),  # SMTP密码
    "MAIL_FROM": os.getenv("MAIL_FROM", "739238103@qq.com"),  # 发件人邮箱
    "MAIL_TO": os.getenv("MAIL_TO", "739238103@qq.com")  # 收件人邮箱
}
