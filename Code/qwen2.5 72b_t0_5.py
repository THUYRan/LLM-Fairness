import os
import glob
import json
import math
import requests
import time
import sys

# Set this index to 1, 2, 3, 4, or 5
SCRIPT_INDEX = 5  # Change this to determine which subset to process (1-5)
mode = 2    #mode=1: 遇到错误时不断重试; mode=2: 遇到错误时自动截取并缩减案情陈述部分
# OpenRouter Configuration
OPENROUTER_API_KEY = "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"  # Replace with your actual API key
MODEL_NAME = "qwen/qwen-2.5-72b-instruct"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Qwen2.5_72b/dateset_for_experiment/"
output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Qwen2.5_72b/output_for_experiment_t0/"
os.makedirs(output_dir, exist_ok=True)  # Ensure output directory exists

input_files = sorted(glob.glob(os.path.join(input_dir, '*_changed.json')))
total_files = len(input_files)

# -------------------------------------------------------------------
# Split files into 5 equal parts
# -------------------------------------------------------------------
num_splits = 5
files_per_split = math.ceil(total_files / num_splits)

# Calculate start and end index for this script
start_idx = (SCRIPT_INDEX - 1) * files_per_split
end_idx = min(start_idx + files_per_split, total_files)

files_to_process = input_files[start_idx:end_idx]
print(files_to_process)

# -------------------------------------------------------------------
# API Request Function
# -------------------------------------------------------------------
def chat_round(messages: list[dict],
               max_new_tokens: int = 100,
               temperature: float = 0.0,
               max_retries: int = 5,
               mode: int = mode) -> str:
    """
    调用 OpenRouter API，
    mode=1: 遇到错误时不断重试
    mode=2: 遇到错误时自动截取并缩减案情陈述部分
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    def extract_case_statement(content: str) -> str:
        match = re.search(r'<案情陈述开始>(.*?)<案情陈述结束>', content, re.DOTALL)
        return match.group(1) if match else None

    def replace_case_statement(content: str, new_case: str) -> str:
        return re.sub(r'(<案情陈述开始>).*?(<案情陈述结束>)',
                      rf'\1{new_case}\2', content, flags=re.DOTALL)

    def truncate_case_statement(case_statement: str, chars_to_remove: int) -> str:
        return case_statement[:-chars_to_remove] if len(case_statement) > chars_to_remove else ""

    attempt = 0
    shorten = 0

    while attempt < max_retries:
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": temperature,
                "provider": {
                    "order": ["DeepInfra","Nebius AI Studio"]
                }
            }
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()

            if 'choices' in response_json:
                if shorten > 0:
                    print("case shortened!")
                return [response_json['choices'][0]['message']['content'].strip(), shorten]

            if mode == 1:
                attempt += 1  # 继续重试
            elif mode == 2:
                shorten = 1
                for message in messages:
                    if message['role'] == 'user':
                        original_content = message['content']
                        case_statement = extract_case_statement(original_content)
                        if case_statement:
                            truncated_case = truncate_case_statement(case_statement, 1500)
                            if not truncated_case:
                                return ["Error: 案情陈述内容过短，无法继续缩减。", shorten]
                            message['content'] = replace_case_statement(original_content, truncated_case)
                attempt += 1
        except requests.RequestException:
            attempt += 1

    return ["API Request failed", shorten]


# -------------------------------------------------------------------
# Processing Loop
# -------------------------------------------------------------------
def generate_predictions(dataset_path: str, donelength: int, batch_size: int = 10) -> list:
    ids, changed_labels, label_values, responses, true_answers = [], [], [], [], []

    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    with open(true_answer_path, 'r', encoding='utf-8') as f:
        true_answer = json.load(f)
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    batch_data = test_data[donelength:min(donelength + batch_size, len(test_data))]

    for idx, data in enumerate(batch_data):
        prompt = data['prompt']
        messages = [{"role": "user", "content": prompt}]
        response = chat_round(messages)
        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        responses.append(response)
        sys.stdout.write(
            f"\rProcessing: {os.path.basename(dataset_path)} [{donelength + idx + 1}/{len(test_data)}] ✅ "
            f"ID: {data['ID']}, Label: {data['changed_label']}"
        )
        sys.stdout.flush()
    return ids, changed_labels, label_values, responses, true_answers


def handle_one_label(dataset_path: str, output_path: str, lendone: int, batch_size: int = 10) -> int:
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    total = len(test_data)

    while lendone < total:
        ids, changed_labels, label_values, responses, true_answers = generate_predictions(dataset_path, lendone,
                                                                                          batch_size)
        if lendone != 0 and os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        for i in range(len(responses)):
            item = {
                "ID": ids[i],
                "changed_label": changed_labels[i],
                "label_value": label_values[i],
                "response": responses[i],
                "true_answer": true_answers[i]
            }
            data.append(item)
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(data, f_out, ensure_ascii=False, indent=4)
        lendone += len(responses)
    print(f"{dataset_path} & {output_path} done!")
    return lendone


def process_file(input_file):
    output_file_name = os.path.basename(input_file).replace('_changed.json', '_qwen25_72b_t0.json')
    output_file = os.path.join(output_dir, output_file_name)
    print(f"\nProcessing File: {input_file}")
    lenofanswer = 0
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            lenofanswer = len(existing_data)
    with open(input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    while lenofanswer < len(test_data):
        lenofanswer = handle_one_label(input_file, output_file, lenofanswer)
    print(f"{input_file} & {output_file} done!")


for file in files_to_process:
    process_file(file)

print(f"Script {SCRIPT_INDEX} finished processing {len(files_to_process)} files.")
