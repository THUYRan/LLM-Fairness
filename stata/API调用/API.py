import re
import subprocess

def modify_and_run(file_path, new_values):
    """
    修改 Python 文件中的指定变量值并执行文件。
    
    :param file_path: 需要修改的 Python 文件路径
    :param new_values: 字典，包含要修改的变量名及其新值
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换变量值
    for var, new_val in new_values.items():
        if isinstance(new_val, str):
            new_val = f'"{new_val}"'
        pattern = rf"{var}\s*=\s*.*"
        replacement = f"{var} = {new_val}"
        content = re.sub(pattern, replacement, content)
    
    # 生成临时文件
    temp_file = file_path.replace('.py', '_modified.py')
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 运行修改后的 Python 文件
    subprocess.run(['python', temp_file], check=True)

# 示例调用
file_path = "/Users/yuki/Desktop/batch/DeepSeek_R1_Example.py"
new_values = {
    "OPENROUTER_API_KEY": "yourAPI",
    "MODEL_NAME": "deepseek/deepseek-r1:free",
    "API_URL": "https://openrouter.ai/api/v1/chat/completions",
    "providers": ["Azure", "Chutes"],
    "output_dir": "/Users/yuki/Desktop/law_ethnics/数据集/v3 - 副本/output_for_experiment/"
}
modify_and_run(file_path, new_values)
