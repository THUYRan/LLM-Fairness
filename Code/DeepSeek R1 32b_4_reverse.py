import os
import glob
import json
import requests  # Using requests instead of torch/transformers
import time
import sys

# =========== OpenRouter Configuration ===========
OPENROUTER_API_KEY = "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"  # Replace with your actual API key
MODEL_NAME = "deepseek/deepseek-r1-distill-qwen-32b"  # OpenRouter DeepSeek model
API_URL = "https://openrouter.ai/api/v1/chat/completions"


# -------------------------------------------------------------------
# Modified chat_round function using OpenRouter API
# -------------------------------------------------------------------
def chat_round(messages: list[dict],
               max_new_tokens: int = 10000,
               temperature: float = 1.0) -> str:
    """
    Calls OpenRouter API with DeepSeek-V3 model and handles errors gracefully.
    If an error occurs, it prints the response, waits for 2 seconds, and retries.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_new_tokens,
        "provider": {
            "order": ["DeepInfra"]
        }
    }

    while True:  # Retry loop
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()  # Raises an HTTPError if the response code is 4xx or 5xx

            response_json = response.json()

            if 'choices' in response_json:
                if "esponse [200" in str(response_json) or response_json is None:
                    print(f"\r🔄 Retrying request...Unable to extract wait seconds.       ",
                          end='', flush=True)
                    #current_provider_idx = (current_provider_idx + 1) % len(providers)
                    times.sleep(3)
                else:
                    return response_json['choices'][0]['message']['content'].strip()
            else:
                print("⚠️ Warning: 'choices' key missing in API response!")
                print("Full Response:", json.dumps(response_json, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"❌ API Request failed: {e}")
            try:
                print("Full Response:", response.text)  # Print raw response for debugging
            except:
                print("Not even response.")
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
def generate_predictions(dataset_path: str, donelength: int, batch_size: int = 10) -> list:
    """
    Reads the dataset and processes it in batches using the OpenRouter API.
    """
    ids, changed_labels, label_values, responses, true_answers = [], [], [], [], []

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
        response = chat_round(messages)

        # Store results
        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        responses.append(response)

        # 4) 更新进度显示
        sys.stdout.write(
            f"\rProcessing: {os.path.basename(dataset_path)} [{donelength + idx + 1}/{len(test_data)}] ✅ "
            f"ID: {data['ID']}, Label: {data['changed_label']}"
        )
        sys.stdout.flush()

    return ids, changed_labels, label_values, responses, true_answers


# -------------------------------------------------------------------
# Function to handle one dataset file in batches
# -------------------------------------------------------------------
def handle_one_label(dataset_path: str, output_path: str, lendone: int, batch_size: int = 10) -> int:
    """
    Processes a dataset file in batches and writes results to an output JSON file.
    """
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    total = len(test_data)

    while lendone < total:
        # Get model predictions
        ids, changed_labels, label_values, responses, true_answers = generate_predictions(dataset_path, lendone,
                                                                                          batch_size)

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
                "true_answer": true_answers[i]
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
input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/dateset_for_experiment/"
output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/output_for_experiment/"
os.makedirs(output_dir, exist_ok=True)
input_files = glob.glob(os.path.join(input_dir, '*_changed.json'))

start_file = r"C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/dateset_for_experiment\defender_political_background_changed.json"  # 你希望从哪个文件之后开始
end_file = r"C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/dateset_for_experiment\defender_ethnicity_changed.json"  # 你希望从哪个文件之后开始
#print(input_files)
if start_file in input_files:
    print('!!!')
    start_index = input_files.index(start_file) + 1  # 找到该文件，并从下一个开始
    end_index = input_files.index(end_file)   # 找到该文件，并从下一个开始
else:
    start_index = 0  # 如果文件不在列表中，则从头开始

input_files = input_files[end_index : start_index]  # 只处理 start_index 之后的文件
print(input_files)

for input_file in reversed(input_files):
    output_file_name = os.path.basename(input_file).replace('_changed.json', '_deepseekr1_32b.json')
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
