import json
import re
import os

# 中文数字到数字的映射字典
chinese_numbers = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
    "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000
}

# 将中文数字转换为阿拉伯数字
def chinese_to_arabic(chinese_str):
    total = 0
    unit = 1  # 当前单位（1: 个, 10: 十, 100: 百）
    num = 0
    for char in reversed(chinese_str):  # 从右往左处理
        if char in chinese_numbers:
            temp = chinese_numbers[char]
            if temp == 10 or temp == 100 or temp == 1000 or temp == 10000:
                if num == 0:
                    num = 1
                total += num * temp
                num = 0
                unit = temp
            else:
                num += temp * unit
        else:
            raise ValueError(f"无法识别的中文字符: {char}")
    total += num
    return total

def clean_response(response_str, file_name, index):
    """清理 `response` 字段中的不必要的符号并将其转换为字典"""
    
    if isinstance(response_str, str):
        # Handle invalid or unnecessary strings
        if response_str == "PROHIBITED_CONTENT" or response_str == "" or response_str.strip() == "```":
            # Handle the invalid or unnecessary response (e.g., return an empty dict or other handling logic)
            return None  # Example: return an empty dictionary
    else:
        # If response_str is already a dictionary, just return it directly without processing
        return response_str


    # 处理反斜杠转义字符
    response_str = response_str.replace("\\", "")

    # 删除 Markdown 格式的 ```json 和 ``` 等符号
    cleaned_response = re.sub(r'```json\n|\n```', '', response_str)
    
    # 处理非法数学表达式（如 15*12, 132,3000）
    cleaned_response = re.sub(r'(\d+)[\*，]\d+', lambda match: str(eval(match.group(0))), cleaned_response)  # 修正类似 15*12
    cleaned_response = re.sub(r'(\d+)[,，](\d+)', r'\1\2', cleaned_response)  # 修正类似 132,3000

    # 处理不完整的或非法的数字格式（如 20"）
    cleaned_response = re.sub(r'(\d+)\"', r'\1', cleaned_response)  # 修正类似 20"

    # 处理中文数字（如 "三年" 转为 "36"）
    def convert_chinese_year(match):
        chinese_year = match.group(1)
        try:
            months = chinese_to_arabic(chinese_year) * 12  # 转换为月数
            return str(months)
        except ValueError:
            return match.group(0)  # 如果无法转换，返回原始字符串

    cleaned_response = re.sub(r'(\d*)([一二三四五六七八九十零]+年)', convert_chinese_year, cleaned_response)
    
    # 处理其他不规范格式，如 "刑期": 15年、18)
    cleaned_response = re.sub(r'(\d+)\)', r'\1', cleaned_response)  # 修正类似 18)

    # 如果 "刑期" 是纯数字字符串（如 "12"），转为数字类型
    cleaned_response = re.sub(r'\"?(\d+)\"?', r'\1', cleaned_response)  # 修正类似 "120" 为 120
    
    # 尝试将字符串转换为 JSON 对象
    try:
        parsed_response = json.loads(cleaned_response)

        # 如果 response 是列表，提取第一个元素
        if isinstance(parsed_response, list):
            if parsed_response:
                parsed_response = parsed_response[0]  # 取第一个元素
        
        return parsed_response

    except json.JSONDecodeError:
        print(f"文件: {file_name}, 索引: {index} 的 `response` 字段转换失败")
        print(f"原始 `response` 内容: {response_str}")
        return None  # 如果解析失败，返回 None 表示此条数据无效

def process_json_file(file_path, output_directory):
    """处理单个 JSON 文件中的数据"""
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            print(f"文件 {file_path} 解析失败")
            return

        # 创建一个新的列表，保存处理后的数据
        new_data = []
        
        for index, item in enumerate(data):
            if 'response' in item:
                cleaned_data = clean_response(item['response'], os.path.basename(file_path), index)
                if cleaned_data is None:
                    continue  # 如果 response 转换失败，跳过该条数据并继续处理下一个
                else:
                    item['response'] = cleaned_data
                    new_data.append(item)  # 只将有效数据添加到 new_data 中

        # 构建新的输出文件路径
        output_file_path = os.path.join(output_directory, f'{os.path.basename(file_path)}')

        # 保存处理后的 JSON 文件到新的路径
        with open(output_file_path, 'w', encoding='utf-8') as out_file:
            json.dump(new_data, out_file, ensure_ascii=False, indent=4)
            print(f"文件 {file_path} 处理完成并已保存为 {output_file_path}")

def process_all_json_files_in_directory(input_directory, output_directory):
    """处理目录下的所有 JSON 文件"""
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for filename in os.listdir(input_directory):
        if filename.endswith('.json'):
            file_path = os.path.join(input_directory, filename)
            process_json_file(file_path, output_directory)

# 处理指定目录下的所有 JSON 文件，并将处理后的文件保存到新的路径
input_directory = r"/Users/yuki/Desktop/law_ethnics/qwen2.5_72b/output_for_experiment" # 替换为实际文件夹路径
output_directory = r"/Users/yuki/Desktop/law_ethnics/qwen2.5_72b/qwen2.5_72b" # 替换为实际的输出文件夹路径
process_all_json_files_in_directory(input_directory, output_directory)
