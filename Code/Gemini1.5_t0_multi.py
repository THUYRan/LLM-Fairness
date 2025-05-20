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
            time.sleep(0.8)
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
    """
    处理一个 data_xxx_changed.json 文件的剩余部分，从 lendone 开始到处理完所有记录。
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
            batch_size=batch_size
        )

        # 读取当前 output_file 进度（若已存在）
        if lendone != 0 and os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []

        # 把最新一批的处理结果追加进去
        for i in range(len(responses)):
            item = {
                "ID": ids[i],
                "changed_label": changed_labels[i],
                "label_value": label_values[i],
                "response": responses[i],
                "true_answer": true_answers[i]
            }
            data.append(item)

        # 写回 output_file
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(data, f_out, ensure_ascii=False, indent=4)

        lendone += len(responses)

    print(f"\n[线程 {script_index}] {dataset_path} & {output_path} done!")
    return lendone


def process_file(input_file: str,
                 api_key: str,
                 output_file: str,
                 mode_setting: int,
                 true_answer_path: str,
                 model_name: str,
                 provider: dict,
                 script_index: int
                 ):
    """
    对单个文件从头到尾进行处理，若部分已处理则从断点继续。
    """
    print(f"\n[线程 {script_index}] Processing File: {input_file}")
    lenofanswer = 0

    # 如果 output_file 存在，读取已完成条数
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            lenofanswer = len(existing_data)

    # 读取原始 input_file 总条数
    with open(input_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    # 若尚未全部处理，则继续处理
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
                   files_to_process: list,
                   mode_setting: int,
                   true_answer_path: str,
                   model_name: str,
                   provider: dict,
                   end_file: str
                   ):
    """
    线程函数：处理分配给该线程的“不完整文件”列表 files_to_process。
    """
    print(f"线程 {script_index} 将处理 {len(files_to_process)} 个未完成文件。")

    for input_file, output_file in files_to_process:
        process_file(
            input_file=input_file,
            api_key=api_key,
            output_file=output_file,
            mode_setting=mode_setting,
            true_answer_path=true_answer_path,
            model_name=model_name,
            provider=provider,
            script_index=script_index
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
    """
    主函数：
    1. 从 input_dir 中获取所有 *_changed.json 文件。
    2. 找到对应的 output 文件（若不存在或尚未处理完，则加入 incomplete_files）。
    3. 将 incomplete_files 均分给 5 个线程。
    4. 启动 5 个线程并等待完成。
    """
    # 如果 output_dir 不存在则创建
    os.makedirs(output_dir, exist_ok=True)

    # 收集所有可能的输入文件
    input_files = sorted(glob.glob(os.path.join(input_dir, '*_changed.json')))

    # 根据 input_file 判断对应 output_file，并检查是否已处理完毕
    incomplete_files = []
    for input_file in input_files:
        output_file_name = os.path.basename(input_file).replace('_changed.json', end_file)
        output_file = os.path.join(output_dir, output_file_name)

        # 如果 output_file 不存在，说明完全没处理，直接加入 incomplete_files
        if not os.path.exists(output_file):
            incomplete_files.append((input_file, output_file))
        else:
            # 如果 output_file 存在，则判断是否已处理完毕
            with open(input_file, 'r', encoding='utf-8') as f_in:
                input_data = json.load(f_in)
            with open(output_file, 'r', encoding='utf-8') as f_out:
                output_data = json.load(f_out)
            # 若记录数小于 input_file，则还没处理完成
            if len(output_data) < len(input_data):
                incomplete_files.append((input_file, output_file))

    if not incomplete_files:
        print("没有需要继续处理的文件，所有文件都已完成。")
        return

    # 替换为各线程实际使用的 API key
    API_KEYS = [
        "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",
        "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",
        "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",
        "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",
        "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"
    ]

    # 将 incomplete_files 均分给 5 个线程
    total_incomplete = len(incomplete_files)
    num_threads = 5
    files_per_thread = math.ceil(total_incomplete / num_threads)

    threads = []
    for i in range(num_threads):
        start_idx = i * files_per_thread
        end_idx = min(start_idx + files_per_thread, total_incomplete)
        # 拆分子列表
        subset = incomplete_files[start_idx:end_idx]
        if not subset:
            break  # 防止最后线程可能分不到内容

        script_index = i + 1
        api_key = API_KEYS[i]
        t = threading.Thread(
            target=run_for_script,
            args=(
                script_index,
                api_key,
                subset,  # 把该子集传给线程
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
    input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Gemini1.5/dateset_for_experiment/"
    output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/Gemini1.5/output_for_experiment_t0/"
    end_file = '_gemini_flash15_t0.json'
    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    mode_setting = 1  # mode_setting=1 表示遇到错误时不断重试；=2 表示自动截取并缩减案情陈述部分

    # 可调整的时停参数，单位：秒
    # 每拿到一个“正常”响应就会 sleep(stop_time) 秒；如果响应中含有 'API Request failed' 就 sleep(5) 秒

    model_name = "google/gemini-flash-1.5"
    provider = {
        "order": ["Google AI Studio"]
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