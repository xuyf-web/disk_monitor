# 磁盘监控工具

这个工具用于监控指定目录的磁盘使用情况，并通过电子邮件发送结构化的报告。

## 功能特点

- 监控指定目录的磁盘使用情况
- 使用多线程处理大型目录，提高效率
- 格式化的文本和HTML邮件报告
- 可配置的警告阈值
- 自动定期运行（通过cron任务）
- 日志记录功能

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

1. 配置文件 `config.json`：
   - `base_path`: 要监控的基础路径
   - `total_disk_size_tb`: 总磁盘大小（TB）
   - `warning_threshold`: 警告阈值百分比
   - `max_workers`: 多线程处理的工作线程数

2. 邮件配置 `.env`（敏感信息）：
   - `SMTP_SERVER`: SMTP服务器地址
   - `SMTP_PORT`: SMTP端口
   - `SMTP_USER`: SMTP用户名
   - `SMTP_PASS`: SMTP密码
   - `MAIL_FROM`: 发件人邮箱
   - `MAIL_TO`: 收件人邮箱

## 使用方法

1. 手动运行磁盘监控并发送邮件：

```bash
python send_disk_usage.py
```

2. 设置cron定时任务：

```bash
crontab -e
```

添加以下内容：

```
0 10 * * 1 cd /data8/xuyf/soft/disk_monitor && python3 send_disk_usage.py >> /data8/xuyf/soft/disk_monitor/cron.log 2>&1
```

这将在每周一上午10点运行脚本。

## 文件说明

- `disk_usage.py`: 用于获取磁盘使用情况的核心模块
- `send_disk_usage.py`: 发送邮件报告的模块
- `mail_config.py`: 邮件配置加载模块
- `config.json`: 项目配置文件
- `.env`: 敏感信息配置文件
- `send_disk_usage.cron`: cron配置示例 