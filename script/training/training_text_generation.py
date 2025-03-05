import os
import csv
import argparse

import numpy as np

from datasets import load_dataset

from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForCausalLM,
    DataCollatorForLanguageModeling,
    TrainingArguments,
    Trainer,
    TextDataset,
    TrainerCallback,
)


def parse_config():
    """
    参数定义
    :return: 参数
    """
    parse = argparse.ArgumentParser(description="Text generation prompt.")
    parse.add_argument(
        "--model_name",
        type=str,
        required=False,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        help="模型名称或路径. 默认是 'deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B'",
    )
    parse.add_argument(
        "--device",
        type=str,
        required=False,
        default="cpu",
        help="程序将会在哪个设备上运行（cpu/cuda）",
    )
    parse.add_argument(
        "--dataset",
        type=str,
        required=False,
        default="",
        help="数据文本、数据集名称或文件名, 支持的文件类型: '.txt' '.csv'",
    )
    parse.add_argument(
        "--using_load_dataset",
        type=bool,
        required=False,
        deufalt=False,
        help="是否使用`datasets`库加载参数`dataset`给定的数据集（如果存在），默认启用",
    )
    return parse.parse_args()


def load_model_and_tokenizer(model_name_or_path, tokenizer_args=None, model_args=None):
    if tokenizer_args is not None:
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, **tokenizer_args)
    else:
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    if model_args is not None:
        model = AutoModelForCausalLM.from_pretrained(model_name_or_path, **model_args)
    else:
        model = AutoModelForCausalLM.from_pretrained(model_name_or_path)
    return tokenizer, model


def read_csv_as_dataset(file_path):
    dataset = []
    with open(file_path, "r", encoding="utf-8") as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            data = {"role": row[0], "context": row[1]}
            dataset.append(data)
    return dataset


def read_txt_as_dataset(file_path):
    dataset = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            data = {"role": line.split(":")[0], "context": line.split(":")[1]}
            dataset.append(data)
    return dataset


def load_datasets(dataset_name, with_load_dataset=False):
    dataset = None
    if with_load_dataset:
        dataset = load_dataset(dataset_name)
        dataset = dataset["train"]
    if os.path.exists(dataset_name):
        dataset = []
        ext_name = os.path.splitext(dataset_name)[1]
        if ext_name == ".csv":
            dataset = read_csv_as_dataset(dataset_name)
        elif ext_name == ".txt":
            dataset = read_txt_as_dataset(dataset_name)
    return dataset


class PrintTrainerCallback(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        _ = logs.pop("total_flos", None)
        if state.is_local_process_zero:
            print(logs)


def main():
    model_path = r"D:/Project/finetune/model/DeepSeek-R1-Distill-Qwen-1.5B/"
    # model_path = r"./model/output/"
    output_path = r"./model/output/"
    device = "cpu"
    dataset_file = "./data/test.txt"
    tokenizer, model = load_model_and_tokenizer(model_path)
    dataset = TextDataset(tokenizer=tokenizer, file_path=dataset_file, block_size=64)
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=False, return_tensors="pt"
    )
    tokenizer.save_pretrained(output_path)
    # model.save_pretrained(output_path)

    training_args = TrainingArguments(
        output_dir=output_path,
        overwrite_output_dir=True,
        num_train_epochs=3,
        use_cpu=True if device == "cpu" else False,
        per_device_train_batch_size=1,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=dataset,
        eval_dataset=dataset,
        callbacks=[PrintTrainerCallback],
    )

    trainer.train()
    trainer.save_model()


main()
# model_path = r"D:/Project/finetune/model/DeepSeek-R1-Distill-Qwen-1.5B/"
# # tokenizer, model = load_model_and_tokenizer()
# tokenizer = AutoTokenizer.from_pretrained(model_path)
# model = AutoModelForCausalLM.from_pretrained(model_path)
# message = [{
#     "role": "user",
#     "content": "法国的首都是哪里？"
# }]
# input = tokenizer.apply_chat_template(message, add_generation_prompt=True, return_tensors="pt")
# out = model.generate(input, max_new_tokens=100, do_sample=True, temperature=0.9, top_p=0.9)
# print(tokenizer.decode(out[0], skip_special_tokens=True))
