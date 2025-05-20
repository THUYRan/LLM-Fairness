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
    mode_param=1: 遇到错误时不断重试
    mode_param=2: 遇到错误时自动截取并缩减案情陈述部分
    返回 [响应内容, 是否缩减案情（缩减次数）]
    """
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


def generate_predictions(dataset_path: str,
                         donelength: int,
                         api_key: str,
                         mode_setting: int,
                         true_answer_path: str,
                         model_name: str,
                         provider: dict,
                         script_index: int,
                         stop_time: float,
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

        # 调用 API 获取 response
        response = chat_round(
            messages,
            api_key=api_key,
            mode_param=mode_setting,
            model_name=model_name,
            provider=provider
        )
        # 如果响应包含 "API Request failed"，则 sleep(5) 后重新跑
        while "equest failed" in response[0]:
            print("!!!!API Request failed Error!!!!!!!")
            time.sleep(5)
            response = chat_round(
                messages,
                api_key=api_key,
                mode_param=mode_setting,
                model_name=model_name,
                provider=provider
            )

        # 正常响应后，休眠 stop_time 秒
        time.sleep(stop_time)

        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        responses.append(response)

        # 输出线程处理进度信息
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
                     stop_time: float,
                     batch_size: int = 10
                     ) -> int:
    """
    连续调用 generate_predictions() 直至所有数据处理完毕。
    lendone 用来记录已经完成的数量（排除 "API Request failed" 已被删除的条目）。
    """
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
            stop_time=stop_time,
            batch_size=batch_size
        )

        # 先尝试读取已有 output，再追加本次结果
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

        # 覆盖写回
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
                 end_file: str,
                 stop_time: float
                 ):
    """
    对单个文件做处理：
      1. 读取 output_file，如有 'API Request failed' 的条目，直接删除；
      2. 根据剩余长度，继续对 test_data 做增量处理。
    """
    output_file_name = os.path.basename(input_file).replace('_changed.json', end_file)
    output_file = os.path.join(output_dir, output_file_name)
    print(f"\n[线程 {script_index}] Processing File: {input_file}")

    # 1) 先读已有的output_file，把包含 "API Request failed" 的条目剔除
    lenofanswer = 0
    filtered_data = []
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        for item in existing_data:
            resp_text = item["response"][0] if item["response"] else ""
            if "API Request failed" in resp_text:
                # 跳过：重新跑
                continue
            else:
                filtered_data.append(item)
        # 再写回过滤后的结果
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(filtered_data, f_out, ensure_ascii=False, indent=4)
        lenofanswer = len(filtered_data)

    # 2) 执行 handle_one_label 继续处理剩余数据
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
            script_index=script_index,
            stop_time=stop_time
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
                   end_file: str,
                   stop_time: float
                   ):
    """
    每个线程处理 input_dir 下的一部分文件。
    """
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
            end_file=end_file,
            stop_time=stop_time
        )
    print(f"线程 {script_index} 完成了所有文件的处理.")


def main(input_dir: str,
         output_dir: str,
         true_answer_path: str,
         mode_setting: int,
         model_name: str,
         provider: dict,
         end_file: str,
         stop_time: float
         ):
    """
    主函数：
      - 确保输出目录存在
      - 创建若干线程分别处理 input_dir 下的文件
      - 每次处理完自动拼接到 output_dir
      - stop_time: 每次拿到成功 response 后需要 sleep(stop_time) 秒
    """
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
                end_file,
                stop_time
            )
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    print("所有线程处理完成！")


if __name__ == '__main__':
    # 在这里设置所有路径和 mode 参数
    input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Qwen2.5_72b/dateset_for_experiment/"
    output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Qwen2.5_72b/output_for_experiment_t0/"
    end_file = '_qwen25_72b_t0.json'
    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    mode_setting = 2  # mode_setting=1 表示遇到错误时不断重试；=2 表示自动截取并缩减案情陈述部分

    # 可调整的时停参数，单位：秒
    # 每拿到一个“正常”响应就会 sleep(stop_time) 秒；如果响应中含有 'API Request failed' 就 sleep(5) 秒
    stop_time = 1.0

    model_name = "qwen/qwen-2.5-72b-instruct"
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
        end_file=end_file,
        stop_time=stop_time
    )
