import os
import glob
import json
import torch
from transformers import AutoTokenizer
from safetensors.torch import load_model
from model import Transformer, ModelArgs
from typing import Any, Dict, List

# 内置路径
CKPT_PATH = "/path/to/DeepSeek-V3"
CONFIG_PATH = "/path/to/config.json"

# 设置环境变量
os.environ["CUDA_VISIBLE_DEVICES"] = '0,1,2,3,4,5,6,7'

def ask_prompt(prompt: str, max_new_tokens: int = 100, temperature: float = 1.0) -> str:
    with open(CONFIG_PATH) as f:
        args = ModelArgs(**json.load(f))
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Transformer(args).to(device)
    tokenizer = AutoTokenizer.from_pretrained(CKPT_PATH)
    load_model(model, f"{CKPT_PATH}/model0-mp1.safetensors")
    
    prompt_tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)
    generated_tokens = generate(model, [prompt_tokens.tolist()[0]], max_new_tokens, tokenizer.eos_token_id, temperature)
    response = tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
    return response

@torch.inference_mode()
def generate(model, prompt_tokens, max_new_tokens, eos_id, temperature):
    prompt_lens = [len(t) for t in prompt_tokens]
    total_len = min(model.max_seq_len, max_new_tokens + max(prompt_lens))
    tokens = torch.full((len(prompt_tokens), total_len), -1, dtype=torch.long, device="cuda")
    for i, t in enumerate(prompt_tokens):
        tokens[i, :len(t)] = torch.tensor(t, dtype=torch.long, device="cuda")
    prev_pos = 0
    finished = torch.tensor([False] * len(prompt_tokens), device="cuda")
    prompt_mask = tokens != -1
    for cur_pos in range(min(prompt_lens), total_len):
        logits = model.forward(tokens[:, prev_pos:cur_pos], prev_pos)
        if temperature > 0:
            next_token = sample(logits, temperature)
        else:
            next_token = logits.argmax(dim=-1)
        next_token = torch.where(prompt_mask[:, cur_pos], tokens[:, cur_pos], next_token)
        tokens[:, cur_pos] = next_token
        finished |= torch.logical_and(~prompt_mask[:, cur_pos], next_token == eos_id)
        prev_pos = cur_pos
        if finished.all():
            break
    completion_tokens = []
    for i, toks in enumerate(tokens.tolist()):
        toks = toks[prompt_lens[i]:prompt_lens[i]+max_new_tokens]
        if eos_id in toks:
            toks = toks[:toks.index(eos_id)]
        completion_tokens.append(toks)
    return completion_tokens

def sample(logits, temperature):
    logits = logits / max(temperature, 1e-5)
    probs = torch.softmax(logits, dim=-1)
    return probs.div_(torch.empty_like(probs).exponential_(1)).argmax(dim=-1)

def generate_predictions(dataset_path: str, donelength: int) -> List:
    ids, changed_labels, label_values, responses, true_answers = [], [], [], [], []

    true_answer_path = "刑期_list.json"
    true_answer = json.load(open(true_answer_path, 'r', encoding='utf-8'))
    test_data = json.load(open(dataset_path, 'r', encoding='utf-8'))

    def process_data(data, ids, changed_labels, label_values, true_answers, responses):
        prompt = data['prompt']
        ids.append(data['ID'])
        changed_labels.append(data['changed_label'])
        label_values.append(data['label_value'])
        true_answers.append(true_answer[data['ID']]["true_answer"])
        reason = ask_prompt(prompt)
        responses.append(reason)

    if donelength >= len(test_data):
        return ids, changed_labels, label_values, responses, true_answers

    for data in test_data[donelength:min(donelength + 100, len(test_data))]:
        process_data(data, ids, changed_labels, label_values, true_answers, responses)

    return ids, changed_labels, label_values, responses, true_answers

def handle_one_label(dataset_path: str, output_path: str, lendone: int) -> None:
    ids, changed_labels, label_values, responses, true_answers = generate_predictions(dataset_path, lendone)
    if lendone != 0:
        data = json.load(open(output_path, 'r', encoding='utf-8'))
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
    torch.cuda.empty_cache()

torch.cuda.empty_cache()
input_dir = "prompts"
output_dir = "llm-judge-result/deepseek"
os.makedirs(output_dir, exist_ok=True)
input_files = glob.glob(os.path.join(input_dir, '*_changed.json'))

for input_file in input_files:
    for i in range(44):
        input_file = input_file
        output_file_name = os.path.basename(input_file).replace('_changed.json', '_deepseek.json')
        output_file = os.path.join(output_dir, output_file_name)
        print(input_file)
        lenofanswer = 0
        if os.path.exists(output_file):
            lenofanswer = len(json.load(open(output_file, 'r', encoding='utf-8')))
        print(f"Already handled {lenofanswer} of {output_file}")
        if lenofanswer < len(json.load(open(input_file, 'r', encoding='utf-8'))):
            handle_one_label(input_file, output_file, lenofanswer)
        else:
            print(f"{input_file} & {output_file} done!")