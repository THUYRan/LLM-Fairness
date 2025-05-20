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
               max_new_tokens: int = 10000,
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
            # 这里可以根据需要 sleep 以防止过快请求被限制
            # time.sleep(0.8)
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

    # 若 max_retries 次都没成功，返回失败
    return ["API Request failed", shorten]


def handle_one_label(dataset_path: str,
                     output_path: str,
                     api_key: str,
                     mode_setting: int,
                     true_answer_path: str,
                     model_name: str,
                     provider: dict,
                     script_index: int,
                     batch_size: int = 10,
                     max_fail_count: int = 3
                     ):
    """
    处理一个 data_xxx_changed.json 文件:
      - 对于同一个 ID 可能有 2~4 条记录(不同 changed_label)，甚至同一个 changed_label 还有不同 label_value。
      - 以 (ID, changed_label, label_value) 作为唯一键来区分、保存和更新。
      - 若已成功则跳过不再请求，若此前失败且 fail_count < max_fail_count 则重试，否则跳过。
      - 处理完后将所有记录合并写回 output_file，不覆盖原先成功的。
    """

    # 1. 读取数据
    with open(dataset_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    with open(true_answer_path, 'r', encoding='utf-8') as f:
        true_answer = json.load(f)

    # 2. 若 output_file 存在则读取已有结果，否则空
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            processed_data = json.load(f)
    else:
        processed_data = []

    # 3. 把 processed_data 放到字典 existing_dict 中，
    #    **改动点：以 (ID, changed_label, label_value) 作为 key**
    existing_dict = {}
    for item in processed_data:
        key = (item["ID"], item["changed_label"], item["label_value"])
        if "fail_count" not in item:
            item["fail_count"] = 0
        existing_dict[key] = item

    # 4. 找出需要处理的记录
    to_process = []
    for record in test_data:
        record_id = record["ID"]
        changed_label = record["changed_label"]
        label_value = record["label_value"]  # 可能会有多种
        key = (record_id, changed_label, label_value)

        if key not in existing_dict:
            # 说明这条记录从未处理过
            to_process.append(record)
        else:
            item = existing_dict[key]
            resp = item["response"]
            fail_cnt = item["fail_count"]

            # 如果之前失败并且还有重试机会，则再试
            if resp[0] == "API Request failed" and fail_cnt < max_fail_count:
                to_process.append(record)
            # 否则(已成功 / 超过失败次数 / 已跳过)就不用处理了

    if not to_process:
        print(f"[线程 {script_index}] 文件 {os.path.basename(dataset_path)} 无需处理（已全部成功或达失败上限）")
        return

    # 5. 分批处理 to_process
    start_idx = 0
    total_to_process = len(to_process)
    while start_idx < total_to_process:
        batch_data = to_process[start_idx:start_idx + batch_size]
        for data in batch_data:
            record_id = data["ID"]
            changed_label = data["changed_label"]
            label_value = data["label_value"]
            key = (record_id, changed_label, label_value)

            # 若字典无此记录，则先初始化
            if key not in existing_dict:
                existing_dict[key] = {
                    "ID": record_id,
                    "changed_label": changed_label,
                    "label_value": label_value,
                    "response": ["Not processed yet", 0],
                    "true_answer": true_answer[record_id]["true_answer"],
                    "fail_count": 0
                }

            current_item = existing_dict[key]
            fail_count = current_item["fail_count"]

            # 如果 fail_count >= max_fail_count，则跳过
            if fail_count >= max_fail_count:
                existing_dict[key]["response"] = [f"Skipping after {max_fail_count} consecutive fails", 0]
                continue

            # 否则调用接口
            prompt = data['prompt']
            messages = [{"role": "user", "content": prompt}]

            response = chat_round(
                messages,
                api_key=api_key,
                mode_param=mode_setting,
                model_name=model_name,
                provider=provider
            )

            # 依结果更新 fail_count
            if response[0] == "API Request failed":
                fail_count += 1
                existing_dict[key]["fail_count"] = fail_count
                if fail_count >= max_fail_count:
                    existing_dict[key]["response"] = [f"Skipping after {max_fail_count} consecutive fails", 0]
                else:
                    existing_dict[key]["response"] = response
            else:
                # 成功则清零
                existing_dict[key]["response"] = response
                existing_dict[key]["fail_count"] = 0

            sys.stdout.write(
                f"\r[线程 {script_index}] ID={record_id}, label={changed_label}, val={label_value}, "
                f"fail_count={existing_dict[key]['fail_count']}       "
            )
            sys.stdout.flush()

        # 每处理完一批，就写回 output_file
        new_data_list = list(existing_dict.values())
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(new_data_list, f_out, ensure_ascii=False, indent=4)

        start_idx += batch_size

    print(f"\n[线程 {script_index}] {dataset_path} -> {output_path} 处理完成！")


def run_for_script(script_index: int,
                   api_key: str,
                   files_to_process: list,
                   mode_setting: int,
                   true_answer_path: str,
                   model_name: str,
                   provider: dict,
                   end_file: str):
    """
    线程函数：处理分配给该线程的 files_to_process，每个元素 (input_file, output_file)。
    """
    print(f"线程 {script_index} 将处理 {len(files_to_process)} 个文件。")

    for input_file, output_file in files_to_process:
        handle_one_label(
            dataset_path=input_file,
            output_path=output_file,
            api_key=api_key,
            mode_setting=mode_setting,
            true_answer_path=true_answer_path,
            model_name=model_name,
            provider=provider,
            script_index=script_index,
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
    2. 判断该文件对应的 output_file 是否需要继续处理：
       - 若 output_file 不存在，肯定要处理；
       - 若 output_file 存在，则判断里面是否有需要重试或尚未出现的记录 (ID, changed_label, label_value)。
    3. 将需要继续处理的文件列表 incomplete_files 均分给 N 个线程并行处理。
    """
    os.makedirs(output_dir, exist_ok=True)

    # 收集所有可能的输入文件
    input_files = sorted(glob.glob(os.path.join(input_dir, '*_changed.json')))

    incomplete_files = []
    for input_file in input_files:
        output_file_name = os.path.basename(input_file).replace('_changed.json', end_file)
        output_file = os.path.join(output_dir, output_file_name)

        if not os.path.exists(output_file):
            # 若不存在 output_file，说明完全没处理过
            incomplete_files.append((input_file, output_file))
        else:
            # 若 output_file 存在，检查是否还有记录需要处理
            with open(input_file, 'r', encoding='utf-8') as f_in:
                input_data = json.load(f_in)
            with open(output_file, 'r', encoding='utf-8') as f_out:
                output_data = json.load(f_out)

            # 转为字典 (ID, changed_label, label_value) -> item
            out_dict = {}
            for item in output_data:
                k = (item["ID"], item["changed_label"], item["label_value"])
                out_dict[k] = item

            need_process = False
            for record in input_data:
                k = (record["ID"], record["changed_label"], record["label_value"])
                if k not in out_dict:
                    # 说明还没处理到这条
                    need_process = True
                    break
                else:
                    resp = out_dict[k]["response"]
                    fail_cnt = out_dict[k].get("fail_count", 0)
                    # 若该条是 failed 且还没到达最大失败次数，则还要继续重试
                    if resp[0] == "API Request failed" and fail_cnt < 3:
                        need_process = True
                        break

            if need_process:
                incomplete_files.append((input_file, output_file))

    if not incomplete_files:
        print("没有需要继续处理的文件，所有文件都已完成或已达失败上限。")
        return

    # 这里根据实际需要配置多线程及对应 API Key
    num_threads = 5
    API_KEYS = [
        "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",
        "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",
        "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",
        "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",
        "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"
    ]

    total_incomplete = len(incomplete_files)
    files_per_thread = math.ceil(total_incomplete / num_threads)

    threads = []
    for i in range(num_threads):
        start_idx = i * files_per_thread
        end_idx = min(start_idx + files_per_thread, total_incomplete)
        subset = incomplete_files[start_idx:end_idx]
        if not subset:
            break

        script_index = i + 1
        api_key = API_KEYS[i]
        t = threading.Thread(
            target=run_for_script,
            args=(
                script_index,
                api_key,
                subset,
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
    # 根据实际情况修改
    input_dir = "C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/dateset_for_experiment/"
    output_dir = "C:/Users/Motick/OneDrive/论文/law ethics/r1 32b/output_for_experiment_t0/"
    end_file = '_r1_32b_t0.json'
    true_answer_path = "C:/Users/Motick/OneDrive/论文/law ethics/刑期_list.json"
    mode_setting = 1  # 1=遇到错误时不断重试; 2=自动截取案情以缩减
    model_name = "deepseek/deepseek-r1-distill-qwen-32b"
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
