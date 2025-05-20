import os
import glob
import json
import requests  # Using requests instead of torch/transformers
import time
import sys

# =========== OpenRouter Configuration ===========
OPENROUTER_API_KEY = "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"  # Replace with your actual API key
MODEL_NAME = "mistralai/mistral-nemo"  # OpenRouter DeepSeek model
API_URL = "https://openrouter.ai/api/v1/chat/completions"


# -------------------------------------------------------------------
# Modified chat_round function using OpenRouter API
# -------------------------------------------------------------------
def chat_round(messages: list[dict],
               max_new_tokens: int = 100,
               temperature: float = 1.0,
               max_retries: int = 5) -> str:
    """
    调用 OpenRouter API，并在检测到输入过长错误时，自动截取并缩减案情陈述部分。
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    def extract_case_statement(content: str) -> str:
        """
        提取 <案情陈述开始> 和 <案情陈述结束> 之间的内容。
        """
        match = re.search(r'<案情陈述开始>(.*?)<案情陈述结束>', content, re.DOTALL)
        return match.group(1) if match else None

    def replace_case_statement(content: str, new_case: str) -> str:
        """
        用新的案情陈述替换原始内容中的案情陈述部分。
        """
        return re.sub(r'(<案情陈述开始>).*?(<案情陈述结束>)',
                      rf'\1{new_case}\2', content, flags=re.DOTALL)

    def truncate_case_statement(case_statement: str, chars_to_remove: int) -> str:
        """
        从案情陈述末尾开始删除指定数量的字符。
        """
        return case_statement[:-chars_to_remove] if len(case_statement) > chars_to_remove else ""

    attempt = 0
    shorten = 0
    while True:
        try:
            while attempt < max_retries:
                payload = {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "temperature": temperature,
                    "provider": {
                        "order": ["DeepInfra"]
                    }
                }
                response = requests.post(API_URL, headers=headers, json=payload)
                response.raise_for_status()

                response_json = response.json()
                if 'choices' in response_json:
                    # print(attempt,shorten)
                    if shorten > 0:
                        print("case shortened!")
                    return [response_json['choices'][0]['message']['content'].strip(), shorten]
                else:
                    shorten = 1
                    for message in messages:
                        if message['role'] == 'user':
                            original_content = message['content']
                            case_statement = extract_case_statement(original_content)
                            if case_statement:
                                # 缩减案情陈述部分
                                truncated_case = truncate_case_statement(case_statement, 1500)
                                # print("case shortened!",str(shorten))
                                if not truncated_case:
                                    return ["Error: 案情陈述内容过短，无法继续缩减。", shorten]
                                # 用缩减后的案情陈述替换原始内容
                                new_content = replace_case_statement(original_content, truncated_case)
                                message['content'] = new_content

                    attempt += 1
                    # time.sleep(2)  # 等待 2 秒后重试
            return [f"API Request failed", shorten]

        except Exception as e:
            print(f"❌ API Request failed: {e}")
            try:
                print("Full Response:", response.text)  # Print raw response for debugging
            except:
                print("Not even Response to print")
            time.sleep(2)  # Wait 2 seconds before retrying
            print("🔄 Retrying request...")


# -------------------------------------------------------------------
# Simplified build_chat_prompt function
# -------------------------------------------------------------------
def build_chat_prompt(messages: list[dict]) -> list[dict]:
    """
    Convert messages to API-compatible format.
    """
    return messages  # No additional formatting needed for OpenRouter


# -------------------------------------------------------------------
# Modified generate_predictions function
# -------------------------------------------------------------------
def generate_predictions(dataset_path: str, donelength: int, batch_size: int = 1) -> list:
    """
    Reads the dataset and processes it in batches using the OpenRouter API.
    """
    ids, changed_labels, label_values, responses, true_answers, shortens = [], [], [], [], [], []

    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    with open(true_answer_path, 'r', encoding='utf-8') as f:
        true_answer = json.load(f)
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    batch_data = test_data[donelength:min(donelength + batch_size, len(test_data))]

    for idx, data in enumerate(batch_data):
        prompt = data['prompt']

        # Construct messages in standard chat format
        messages = [{"role": "user", "content": prompt}]

        # Get API response
        response, shorten = chat_round(messages)
        # print("传回的shorten",str(shorten))

        # Store results
        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        responses.append(response)
        shortens.append(shorten)
        # 4) 更新进度显示
        sys.stdout.write(
            f"\rProcessing: {os.path.basename(dataset_path)} [{donelength + idx + 1}/{len(test_data)}] ✅ "
            f"ID: {data['ID']}, Label: {data['changed_label']}"
        )
        sys.stdout.flush()

    return ids, changed_labels, label_values, responses, true_answers, shortens


# -------------------------------------------------------------------
# Function to handle one dataset file in batches
# -------------------------------------------------------------------
def handle_one_label(dataset_path: str, output_path: str, lendone: int, batch_size: int = 20) -> int:
    """
    Processes a dataset file in batches and writes results to an output JSON file.
    """
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    total = len(test_data)

    while lendone < total:
        # Get model predictions
        ids, changed_labels, label_values, responses, true_answers, shortens = generate_predictions(dataset_path,
                                                                                                    lendone, batch_size)

        # Read existing output file if available
        if lendone != 0 and os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []

        # Append new results
        for i in range(len(responses)):
            item = {
                "ID": ids[i],
                "changed_label": changed_labels[i],
                "label_value": label_values[i],
                "response": responses[i],
                "true_answer": true_answers[i],
                "truncation": shortens[i]
            }
            data.append(item)

        # Write updated results to output file
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(data, f_out, ensure_ascii=False, indent=4)

        # Update completed count
        lendone += len(responses)

        # print(f"Handled {lendone} of {total} in {output_path}")

    print(f"{dataset_path} & {output_path} done!")
    return lendone


# -------------------------------------------------------------------
# Batch Processing Entry Point
# -------------------------------------------------------------------
input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Mistral Nemo/dateset_for_experiment/"
output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Mistral Nemo/output_for_experiment/"
os.makedirs(output_dir, exist_ok=True)
input_files = glob.glob(os.path.join(input_dir, '*_changed.json'))

for input_file in input_files:
    output_file_name = os.path.basename(input_file).replace('_changed.json', '_deepseek.json')
    output_file = os.path.join(output_dir, output_file_name)

    print(f"\nProcessing File: {input_file}")

    lenofanswer = 0
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            lenofanswer = len(existing_data)

    # print(f"Already handled {lenofanswer} of {input_file}")

    # If there are remaining entries, process them
    with open(input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    while lenofanswer < len(test_data):
        lenofanswer = handle_one_label(input_file, output_file, lenofanswer)

    print(f"{input_file} & {output_file} done!")
