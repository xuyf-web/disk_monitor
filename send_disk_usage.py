import smtplib
import subprocess
import logging
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pathlib import Path
from datetime import datetime

# 导入邮件配置
from mail_config import MAIL_CONFIG
import disk_usage

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='disk_monitor.log'
)
logger = logging.getLogger('mail_sender')

# 添加终端日志处理器，方便调试
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

def convert_to_html(text):
    """将纯文本转换为HTML格式"""
    lines = text.split('\n')
    
    # 准备HTML头部
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h2 { color: #333366; }
            h3 { color: #333366; margin-top: 30px; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; }
            th { background-color: #f2f2f2; text-align: left; }
            td.size, th.size { text-align: right; }
            td.percent, th.percent { text-align: right; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .warning { color: red; font-weight: bold; }
            .summary { margin-top: 20px; margin-bottom: 30px; }
            .section { margin-bottom: 40px; }
        </style>
    </head>
    <body>
    """
    
    # 添加标题
    if lines and lines[0].strip():
        html += f'<h2>{lines[0]}</h2>\n'
    
    # 状态变量
    in_section = False  # 是否在处理一个区域
    current_section = ""  # 当前区域标题
    in_table = False  # 是否在处理表格
    table_rows = []  # 表格行
    headers = []  # 表头
    summary_lines = []  # 摘要文本
    
    # 处理每一行
    i = 1  # 从第二行开始（跳过标题）
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过空行
        if not line:
            i += 1
            continue
        
        # 检测区域开始
        if line.startswith("==") and line.endswith("=="):
            # 如果正在处理一个区域，先结束它
            if in_section:
                # 添加之前区域的摘要信息
                if summary_lines:
                    html += '<div class="summary">\n'
                    for summary_line in summary_lines:
                        if "WARNING" in summary_line:
                            html += f'<p class="warning">{summary_line}</p>\n'
                        else:
                            html += f'<p>{summary_line}</p>\n'
                    html += '</div>\n'
                
                html += '</div>\n'  # 结束前一个区域
            
            # 开始新区域
            current_section = line.strip("= ")
            html += f'<div class="section">\n'
            html += f'<h3>{current_section}</h3>\n'
            in_section = True
            in_table = False
            table_rows = []
            headers = []
            summary_lines = []
            i += 1
            continue
        
        # 检测表格边框
        if line.startswith("+--") and "-+" in line:
            if not in_table:
                # 表格开始
                in_table = True
                i += 1
                
                # 获取表头
                if i < len(lines):
                    header_line = lines[i].strip()
                    if "|" in header_line:
                        headers = [h.strip() for h in header_line.split('|') if h.strip()]
                        i += 1
                    
                    # 跳过表头下方的分隔行
                    if i < len(lines) and lines[i].strip().startswith("+--"):
                        i += 1
                
                # 开始构建表格
                if headers:
                    html += '<table>\n<tr>\n'
                    for header in headers:
                        html += f'<th>{header}</th>\n'
                    html += '</tr>\n'
            else:
                # 表格结束
                in_table = False
                
                # 添加表格数据
                for row_data in table_rows:
                    html += '<tr>\n'
                    for j, cell in enumerate(row_data):
                        if j == 0:  # 目录名
                            html += f'<td>{cell}</td>\n'
                        else:  # 大小和百分比（右对齐）
                            html += f'<td align="right">{cell}</td>\n'
                    html += '</tr>\n'
                
                html += '</table>\n'
                table_rows = []
                i += 1
                continue
        
        # 处理表格数据行
        if in_table and "|" in line:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                table_rows.append(cells)
            i += 1
            continue
        
        # 处理摘要信息
        if in_section and not in_table:
            summary_lines.append(line)
            i += 1
            continue
        
        # 其他情况，直接处理为普通段落
        if not in_section:
            html += f'<p>{line}</p>\n'
        
        i += 1
    
    # 处理最后一个区域
    if in_section:
        # 添加摘要信息
        if summary_lines:
            html += '<div class="summary">\n'
            for line in summary_lines:
                if "WARNING" in line:
                    html += f'<p class="warning">{line}</p>\n'
                else:
                    html += f'<p>{line}</p>\n'
            html += '</div>\n'
        
        html += '</div>\n'  # 结束区域
    
    # 添加注意事项
    html += """
        <h3>请注意：</h3>
        <ul>
            <li>使用率超过警告阈值时将收到红色警告</li>
            <li>报告每周自动生成</li>
            <li>如有异常请联系系统管理员</li>
        </ul>
    </body>
    </html>
    """
    
    return html

def send_mail(subject, content, html_content=None):
    """发送邮件，支持HTML格式"""
    try:
        logger.info(f"准备发送邮件，配置：{MAIL_CONFIG['SMTP_SERVER']}:{MAIL_CONFIG['SMTP_PORT']}")
        
        # 创建多部分邮件
        msg = MIMEMultipart('alternative')
        msg['From'] = MAIL_CONFIG['MAIL_FROM']
        msg['To'] = MAIL_CONFIG['MAIL_TO']
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 添加纯文本内容
        text_part = MIMEText(content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # 如果有HTML内容，添加HTML部分
        if html_content:
            # 确保HTML内容正确设置charset
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            logger.info("已添加HTML格式内容到邮件")
        
        logger.info("尝试连接SMTP服务器...")
        
        # 选择合适的SMTP连接方式
        try:
            # 尝试使用SSL连接
            try:
                smtp = smtplib.SMTP_SSL(MAIL_CONFIG['SMTP_SERVER'], 465, timeout=10)
                logger.info("使用SSL连接SMTP服务器成功")
            except:
                # 如果SSL连接失败，回退到普通连接
                logger.info("SSL连接失败，尝试普通连接...")
                smtp = smtplib.SMTP(MAIL_CONFIG['SMTP_SERVER'], MAIL_CONFIG['SMTP_PORT'], timeout=10)
                smtp.starttls()
                logger.info("使用普通连接并启用TLS成功")
            
            logger.info(f"尝试登录邮箱：{MAIL_CONFIG['SMTP_USER']}")
            smtp.login(MAIL_CONFIG['SMTP_USER'], MAIL_CONFIG['SMTP_PASS'])
            logger.info("登录成功，发送邮件...")
            
            smtp.sendmail(MAIL_CONFIG['MAIL_FROM'], [MAIL_CONFIG['MAIL_TO']], msg.as_string())
            smtp.quit()
            logger.info("邮件发送成功")
            return True
        except Exception as e:
            logger.error(f"SMTP操作失败: {str(e)}")
            # 尝试使用其他端口
            alternate_ports = [25, 2525, 587]
            for port in alternate_ports:
                if port != MAIL_CONFIG['SMTP_PORT']:
                    try:
                        logger.info(f"尝试使用备用端口 {port}...")
                        smtp = smtplib.SMTP(MAIL_CONFIG['SMTP_SERVER'], port, timeout=10)
                        smtp.starttls()
                        smtp.login(MAIL_CONFIG['SMTP_USER'], MAIL_CONFIG['SMTP_PASS'])
                        smtp.sendmail(MAIL_CONFIG['MAIL_FROM'], [MAIL_CONFIG['MAIL_TO']], msg.as_string())
                        smtp.quit()
                        logger.info(f"使用端口 {port} 发送成功")
                        return True
                    except Exception as inner_e:
                        logger.error(f"使用端口 {port} 失败: {str(inner_e)}")
            raise Exception("所有SMTP连接方式都失败")
            
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        # 打印详细错误信息
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def save_report_to_file(report, html):
    """将报告保存到文件中，作为邮件发送失败的备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 文件名
    text_file = f"report_{timestamp}.txt"
    html_file = f"report_{timestamp}.html"
    
    # 保存文本报告
    try:
        with open(text_file, "w") as f:
            f.write(report)
        logger.info(f"文本报告已保存到 {text_file}")
    except Exception as e:
        logger.error(f"保存文本报告失败: {str(e)}")
    
    # 保存HTML报告
    try:
        with open(html_file, "w") as f:
            f.write(html)
        logger.info(f"HTML报告已保存到 {html_file}")
    except Exception as e:
        logger.error(f"保存HTML报告失败: {str(e)}")
        
    return text_file, html_file

def delete_report_files(text_file, html_file):
    """删除报告文件"""
    try:
        if os.path.exists(text_file):
            os.remove(text_file)
            logger.info(f"已删除文本报告文件: {text_file}")
    except Exception as e:
        logger.error(f"删除文本报告文件失败: {str(e)}")
        
    try:
        if os.path.exists(html_file):
            os.remove(html_file)
            logger.info(f"已删除HTML报告文件: {html_file}")
    except Exception as e:
        logger.error(f"删除HTML报告文件失败: {str(e)}")

def clean_old_report_files():
    """清理所有旧的报告文件"""
    try:
        report_files = []
        current_dir = Path('.')
        
        # 查找所有report_开头的txt和html文件
        txt_files = list(current_dir.glob('report_*.txt'))
        html_files = list(current_dir.glob('report_*.html'))
        report_files = txt_files + html_files
        
        if not report_files:
            logger.info("没有找到旧的报告文件")
            return
            
        # 删除找到的文件
        count = 0
        for file in report_files:
            try:
                os.remove(file)
                count += 1
                logger.debug(f"已删除旧报告文件: {file}")
            except Exception as e:
                logger.warning(f"删除文件 {file} 失败: {str(e)}")
        
        logger.info(f"已清理 {count} 个旧报告文件")
    except Exception as e:
        logger.error(f"清理旧报告文件时出错: {str(e)}")

def save_last_success_report(text_file, html_file):
    """保存最后一次成功的报告，便于历史查看"""
    try:
        # 复制文本报告
        if os.path.exists(text_file):
            with open(text_file, 'r') as src:
                content = src.read()
                with open('last_report.txt', 'w') as dst:
                    dst.write(content)
            logger.info("已保存最后一次文本报告至 last_report.txt")
        
        # 复制HTML报告
        if os.path.exists(html_file):
            with open(html_file, 'r') as src:
                content = src.read()
                with open('last_report.html', 'w') as dst:
                    dst.write(content)
            logger.info("已保存最后一次HTML报告至 last_report.html")
    except Exception as e:
        logger.error(f"保存最后一次报告失败: {str(e)}")

def main():
    """主函数：获取磁盘使用情况并发送邮件"""
    logger.info("开始执行磁盘监控任务")
    
    # 清理旧报告文件
    clean_old_report_files()
    
    try:
        # 直接调用disk_usage模块获取报告
        usage_report = disk_usage.main()
        
        if not usage_report:
            logger.error("未能获取磁盘使用报告")
            return
        
        # 准备邮件内容
        subject = f"磁盘使用情况报告 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # 添加一些额外说明
        content = f"{usage_report}\n\n请注意：\n- 使用率超过阈值时将收到警告\n- 报告每周自动生成\n- 如有异常请联系系统管理员"
        
        # 转换为HTML格式
        html_content = convert_to_html(usage_report)
        
        # 保存报告到文件（作为备份）
        text_file, html_file = save_report_to_file(content, html_content)
        
        # 保存最后一次成功的报告（用于历史查看）
        save_last_success_report(text_file, html_file)
        
        # 发送邮件
        mail_sent = send_mail(subject, content, html_content)
        
        if mail_sent:
            # 邮件发送成功后删除临时文件
            delete_report_files(text_file, html_file)
        else:
            logger.warning("邮件发送失败，但报告已保存到文件中。请检查SMTP配置。")
        
    except Exception as e:
        logger.error(f"执行过程中出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
