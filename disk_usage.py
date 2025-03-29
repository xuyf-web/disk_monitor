import os
import subprocess
import json
from prettytable import PrettyTable
from pathlib import Path
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='disk_monitor.log'
)
logger = logging.getLogger('disk_monitor')

# 默认配置
DEFAULT_CONFIG = {
    "monitored_paths": [
        {
            "path": "/data8/xuyf",
            "name": "数据分区",
            "total_size_tb": 5,
            "warning_threshold": 80
        },
        {
            "path": "/home2/xuyf",
            "name": "用户主目录",
            "total_size_gb": 5,
            "warning_threshold": 80
        }
    ],
    "max_workers": 4
}

def load_config():
    """加载配置文件，如果不存在则使用默认配置"""
    config_path = Path(__file__).parent / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    return DEFAULT_CONFIG

def get_dir_size(path):
    """获取目录大小（单位：字节）"""
    try:
        result = subprocess.run(['du', '-sb', path], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               timeout=300)  # 添加超时设置
        if result.returncode == 0:
            return int(result.stdout.split()[0])
        else:
            logger.error(f"获取目录大小失败: {path}, 错误: {result.stderr.decode()}")
            return 0
    except Exception as e:
        logger.error(f"获取目录大小异常: {path}, 错误: {str(e)}")
        return 0

def format_size(size_bytes):
    """将字节数转换为最合适的单位"""
    units = ['B', 'K', 'M', 'G', 'T', 'P']
    size = float(size_bytes)
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}"

def analyze_path(path_config, max_workers=4):
    """分析单个路径的磁盘使用情况"""
    path = path_config["path"]
    name = path_config.get("name", os.path.basename(path))
    # 计算总容量（字节）
    if "total_size_tb" in path_config:
        total_bytes = path_config["total_size_tb"] * 1024 ** 4  # TB转换为字节
    elif "total_size_gb" in path_config:
        total_bytes = path_config["total_size_gb"] * 1024 ** 3  # GB转换为字节
    else:
        total_bytes = 5 * 1024 ** 4  # 默认5TB
    
    warning_threshold = path_config.get("warning_threshold", 80)
    
    logger.info(f"开始分析目录: {path}")
    
    # 获取所有一级子目录
    try:
        base_path = Path(path)
        directories = [item for item in base_path.iterdir() if item.is_dir()]
    except Exception as e:
        logger.error(f"读取目录 {path} 失败: {str(e)}")
        return {
            "name": name,
            "path": path,
            "error": f"读取目录失败: {str(e)}",
            "total_bytes": 0,
            "directories": [],
            "total_capacity": total_bytes,
            "usage_percent": 0,
            "warning_threshold": warning_threshold
        }
    
    # 使用线程池并行获取目录大小
    dir_sizes = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_dir = {executor.submit(get_dir_size, str(d)): d for d in directories}
        for future in future_to_dir:
            directory = future_to_dir[future]
            try:
                size_bytes = future.result()
                dir_sizes.append((directory.name, size_bytes))
            except Exception as e:
                logger.error(f"处理目录 {directory} 时出错: {str(e)}")
    
    # 按大小排序
    dir_sizes.sort(key=lambda x: x[1], reverse=True)
    
    # 计算总大小
    total_size = sum(size for _, size in dir_sizes)
    
    # 计算使用率
    usage_percent = (total_size / total_bytes) * 100 if total_bytes > 0 else 0
    
    # 构建目录数据
    directories_data = []
    for dir_name, size_bytes in dir_sizes:
        directories_data.append({
            "name": dir_name,
            "size_bytes": size_bytes,
            "formatted_size": format_size(size_bytes),
            "percentage": (size_bytes / total_bytes) * 100 if total_bytes > 0 else 0
        })
    
    # 返回分析结果
    return {
        "name": name,
        "path": path,
        "directories": directories_data,
        "total_size": total_size,
        "formatted_total_size": format_size(total_size),
        "total_capacity": total_bytes,
        "formatted_capacity": format_size(total_bytes),
        "usage_percent": usage_percent,
        "warning_threshold": warning_threshold,
        "has_warning": usage_percent > warning_threshold
    }

def generate_report(path_results):
    """生成报告"""
    report_lines = []
    current_date = datetime.now().strftime("%Y-%m-%d")
    report_lines.append(f"Disk Usage Report for {current_date}:")
    report_lines.append("")
    
    # 为每个监控的路径生成表格
    for result in path_results:
        if "error" in result:
            report_lines.append(f"Error analyzing {result['name']} ({result['path']}): {result['error']}")
            report_lines.append("")
            continue
        
        # 添加分区标题
        report_lines.append(f"== {result['name']} ({result['path']}) ==")
        
        # 创建表格
        table = PrettyTable()
        table.field_names = ["Directory", "Size", "Percentage"]
        table.align["Directory"] = "l"
        table.align["Size"] = "r"
        table.align["Percentage"] = "r"
        
        # 添加目录数据
        for dir_data in result["directories"]:
            table.add_row([
                dir_data["name"], 
                dir_data["formatted_size"],
                f"{dir_data['percentage']:.2f}%"
            ])
        
        report_lines.append(str(table))
        
        # 添加总结信息
        report_lines.append(f"\nTotal Size: {result['formatted_total_size']}")
        report_lines.append(f"Disk Capacity: {result['formatted_capacity']}")
        report_lines.append(f"Usage Percentage: {result['usage_percent']:.2f}%")
        
        # 添加警告（如果超过阈值）
        if result["has_warning"]:
            report_lines.append(f"\nWARNING: Disk usage exceeds {result['warning_threshold']}%!")
        
        report_lines.append("")  # 空行分隔不同路径的报告
    
    logger.info(f"磁盘使用报告已生成")
    return "\n".join(report_lines)

def main():
    """主函数：获取磁盘使用情况并生成报告"""
    config = load_config()
    monitored_paths = config.get("monitored_paths", DEFAULT_CONFIG["monitored_paths"])
    max_workers = config.get("max_workers", DEFAULT_CONFIG["max_workers"])
    
    # 分析每个监控的路径
    path_results = []
    for path_config in monitored_paths:
        result = analyze_path(path_config, max_workers)
        path_results.append(result)
        
        # 记录警告信息
        if result.get("has_warning", False):
            logger.warning(f"{result['name']} 磁盘使用率达到 {result['usage_percent']:.2f}%, 超过警告阈值 {result['warning_threshold']}%")
    
    # 生成报告
    report = generate_report(path_results)
    
    return report

if __name__ == "__main__":
    report = main()
    if report:
        print(report)
