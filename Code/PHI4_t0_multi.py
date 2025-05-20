import os
import glob
import json
import math
import requests
import time
import sys
import re
import threading

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def chat_round(messages: list[dict],
               api_key: str,
               mode_param: int,
               model_name: str,
               provider: dict,
               max_new_tokens: int = 100,
               temperature: float = 0.0,
               max_retries: int = 5
               ) -> list:
    """
    调用 OpenRouter API

    mode_param == 1: 遇到错误时不断重试，遇到错误时自动缩减案情陈述部分（如果有）
                     返回格式：[响应内容, 是否缩减（缩减次数）]
    mode_param == 2: 采用更优雅的错误处理方式，使用 transforms 参数，并无限重试
                     返回格式：[响应内容, 0]
    """
    if mode_param == 1:
        # 保留原有逻辑：如遇到错误则不断重试或自动缩减案情陈述部分
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        def extract_case_statement(content: str) -> str:
            match = re.search(r'<案情陈述开始>(.*?)<案情陈述结束>', content, re.DOTALL)
            return match.group(1) if match else None

        def replace_case_statement(content: str, new_case: str) -> str:
            return re.sub(
                r'(<案情陈述开始>).*?(<案情陈述结束>)',
                rf'\1{new_case}\2',
                content,
                flags=re.DOTALL
            )

        def truncate_case_statement(case_statement: str, chars_to_remove: int) -> str:
            return case_statement[:-chars_to_remove] if len(case_statement) > chars_to_remove else ""

        attempt = 0
        shorten = 0

        while attempt < max_retries:
            try:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_new_tokens": max_new_tokens,
                    "provider": provider
                }
                response = requests.post(API_URL, headers=headers, json=payload)
                response.raise_for_status()
                response_json = response.json()

                if 'choices' in response_json:
                    if shorten > 0:
                        print("case shortened!")
                    return [response_json['choices'][0]['message']['content'].strip(), shorten]

                # 如果 API 返回内容不符合预期
                if mode_param == 1:
                    attempt += 1  # 继续重试
                elif mode_param == 2:
                    # 本分支在 mode==1 内理论上不会走到
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

    elif mode_param == 2:
        # 采用更优雅的错误处理逻辑，使用 transforms 参数，并无限重试
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 注意：这里将参数名 max_new_tokens 转换为 max_tokens 以符合 API 要求
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_new_tokens,
            "transforms": ["middle-out"],
            "provider": provider  # 若需要固定使用 {"order": ["Lambda"]} 可修改此处
        }

        while True:
            try:
                response = requests.post(API_URL, headers=headers, json=payload)
                response.raise_for_status()  # 如果响应码为 4xx 或 5xx，则抛出异常
                response_json = response.json()

                if 'choices' in response_json:
                    return [response_json['choices'][0]['message']['content'].strip(), 0]
                else:
                    print("⚠️ Warning: 'choices' key missing in API response!")
                    if "maximum context length" in str(response_json):
                        warn = "Input too long. Pass."
                        print(warn)
                        return [warn, 0]
                    else:
                        print("Full Response:", json.dumps(response_json, indent=2, ensure_ascii=False))
                        print("Some other error occurred.")
                        time.sleep(10)
            except Exception as e:
                print(f"❌ API Request failed: {e}")
                try:
                    print("Full Response:", response.text)
                except Exception:
                    print("Not even Response to print")
                time.sleep(2)
                print("🔄 Retrying request...")

    else:
        return ["Invalid mode_param", 0]

def generate_predictions(dataset_path: str,
                         donelength: int,
                         api_key: str,
                         mode_setting: int,
                         true_answer_path: str,
                         model_name: str,
                         provider: dict,
                         script_index: int,
                         batch_size: int = 10
                         ) -> tuple:
    ids, changed_labels, label_values, responses, true_answers = [], [], [], [], []

    with open(true_answer_path, 'r', encoding='utf-8') as f:
        true_answer = json.load(f)
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    batch_data = test_data[donelength:min(donelength + batch_size, len(test_data))]

    for idx, data in enumerate(batch_data):
        prompt = data['prompt']
        messages = [{"role": "user", "content": prompt}]
        response = chat_round(
            messages,
            api_key=api_key,
            mode_param=mode_setting,
            model_name=model_name,
            provider=provider
        )
        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        responses.append(response)

        # 在这里输出线程编号信息
        sys.stdout.write(
            f"\r[线程 {script_index}] Processing: {os.path.basename(dataset_path)} "
            f"[{donelength + idx + 1}/{len(test_data)}] ✅ "
            f"ID: {data['ID']}, Label: {data['changed_label']}"
        )
        sys.stdout.flush()
    return ids, changed_labels, label_values, responses, true_answers


def handle_one_label(dataset_path: str,
                     output_path: str,
                     lendone: int,
                     api_key: str,
                     mode_setting: int,
                     true_answer_path: str,
                     model_name: str,
                     provider: dict,
                     script_index: int,
                     batch_size: int = 10
                     ) -> int:
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    total = len(test_data)

    while lendone < total:
        (ids,
         changed_labels,
         label_values,
         responses,
         true_answers) = generate_predictions(
            dataset_path=dataset_path,
            donelength=lendone,
            api_key=api_key,
            mode_setting=mode_setting,
            true_answer_path=true_answer_path,
            model_name=model_name,
            provider=provider,
            script_index=script_index,
            batch_size=batch_size
        )

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

    print(f"\n[线程 {script_index}] {dataset_path} & {output_path} done!")
    return lendone


def process_file(input_file: str,
                 api_key: str,
                 output_dir: str,
                 mode_setting: int,
                 true_answer_path: str,
                 model_name: str,
                 provider: dict,
                 script_index: int,
                 end_file: str
                 ):
    output_file_name = os.path.basename(input_file).replace('_changed.json', end_file)
    output_file = os.path.join(output_dir, output_file_name)
    print(f"\n[线程 {script_index}] Processing File: {input_file}")
    lenofanswer = 0

    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            lenofanswer = len(existing_data)

    with open(input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    while lenofanswer < len(test_data):
        lenofanswer = handle_one_label(
            dataset_path=input_file,
            output_path=output_file,
            lendone=lenofanswer,
            api_key=api_key,
            mode_setting=mode_setting,
            true_answer_path=true_answer_path,
            model_name=model_name,
            provider=provider,
            script_index=script_index
        )
    print(f"[线程 {script_index}] {input_file} & {output_file} done!")


def run_for_script(script_index: int,
                   api_key: str,
                   input_dir: str,
                   output_dir: str,
                   mode_setting: int,
                   true_answer_path: str,
                   model_name: str,
                   provider: dict,
                   end_file: str
                   ):
    # 将输入文件均分成 5 份，每个线程只处理对应的子集
    input_files = sorted(glob.glob(os.path.join(input_dir, '*_changed.json')))
    total_files = len(input_files)
    num_splits = 5
    files_per_split = math.ceil(total_files / num_splits)
    start_idx = (script_index - 1) * files_per_split
    end_idx = min(start_idx + files_per_split, total_files)
    files_to_process = input_files[start_idx:end_idx]

    print(f"线程 {script_index} 将处理 {len(files_to_process)} 个文件: {files_to_process}")

    for file in files_to_process:
        process_file(
            input_file=file,
            api_key=api_key,
            output_dir=output_dir,
            mode_setting=mode_setting,
            true_answer_path=true_answer_path,
            model_name=model_name,
            provider=provider,
            script_index=script_index,
            end_file=end_file
        )
    print(f"线程 {script_index} 完成了所有文件的处理.")


def main(input_dir: str,
         output_dir: str,
         true_answer_path: str,
         mode_setting: int,
         model_name: str,
         provider: dict,
         end_file: str
         ):
    # 如果 output_dir 不存在则创建
    os.makedirs(output_dir, exist_ok=True)

    # 替换为各线程实际使用的 API key
    API_KEYS = [
        "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",
        "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",
        "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",
        "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",
        "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"
    ]

    threads = []
    for i in range(5):
        script_index = i + 1
        api_key = API_KEYS[i]
        t = threading.Thread(
            target=run_for_script,
            args=(
                script_index,
                api_key,
                input_dir,
                output_dir,
                mode_setting,
                true_answer_path,
                model_name,
                provider,
                end_file
            )
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    print("所有线程处理完成！")


if __name__ == '__main__':
    # 在这里设置所有路径和 mode 参数
    input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/PHI4/dateset_for_experiment/"
    output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/PHI4/output_for_experiment_t0/"
    end_file = 'phi4_t0.json'
    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    mode_setting = 2  # mode_setting=1 表示遇到错误时不断重试；=2 表示自动截取并缩减案情陈述部分

    model_name = "microsoft/phi-4"
    provider = {
        "order": ["DeepInfra"]
    }

    main(
        input_dir=input_dir,
        output_dir=output_dir,
        true_answer_path=true_answer_path,
        mode_setting=mode_setting,
        model_name=model_name,
        provider=provider,
        end_file=end_file
    )
