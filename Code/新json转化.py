import os
import json
import re

def process_response(response):
    try:
        # 检查response格式是否符合预期
        if not isinstance(response, list) or len(response) < 2:
            return response
        
        response_str = response[0]
        truncation_value = response[1]
        
        # 使用正则表达式提取JSON对象
        json_match = re.search(r'\{.*?\}', response_str, re.DOTALL)
        if not json_match:
            return response
        
        # 解析提取的JSON内容
        extracted_json = json.loads(json_match.group())
        
        # 创建新的response结构
        new_response = extracted_json.copy()
        new_response["truncation"] = truncation_value
        
        return new_response
    except Exception:
        # 出现任何错误时返回原始response
        return response

def process_json_files(input_dir, output_dir):
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 遍历输入目录中的所有JSON文件
    for filename in os.listdir(input_dir):
        if not filename.endswith('.json'):
            continue
        
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)
        
        try:
            # 读取原始JSON文件
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理每个JSON对象
            processed_data = []
            for item in data:
                original_response = item.get('response', [])
                processed_response = process_response(original_response)
                item['response'] = processed_response
                processed_data.append(item)
            
            # 写入处理后的文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
            print(f"成功处理文件：{filename}")
            
        except Exception as e:
            print(f"处理文件 {filename} 时出错：{str(e)}")
            continue


# 示例：指定输入文件夹和输出文件夹路径
input_folder = r"C:\Users\86158\Desktop\15bias model\MistralNemo_t0\output_for_experiment_t0" # 你的原始JSON文件夹路径
output_folder = r"C:\Users\86158\Desktop\15bias model\MistralNemo_t0\MistralNemo_t0" # 转换后JSON文件保存路径
process_json_files(input_folder, output_folder)
