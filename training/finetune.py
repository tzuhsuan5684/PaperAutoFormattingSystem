"""
Week 2 — QLoRA Fine-tune Qwen2.5-1.5B（Unsloth + TRL）
執行方式（建議在 Colab GPU 環境）：
    python training/finetune.py --config training/config.yaml

Colab 快速啟動：
    !pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    !pip install trl peft accelerate bitsandbytes datasets
    !python training/finetune.py
"""

import json
import os
import sys
from pathlib import Path

import yaml
from loguru import logger


# ── Prompt 模板 ───────────────────────────────────────────────────────────────
ALPACA_TEMPLATE = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

ALPACA_TEMPLATE_NO_INPUT = """Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Response:
{output}"""


def format_prompt(example: dict, eos_token: str = "") -> str:
    if example.get("input", "").strip():
        text = ALPACA_TEMPLATE.format(
            instruction=example["instruction"],
            input=example["input"],
            output=example["output"],
        )
    else:
        text = ALPACA_TEMPLATE_NO_INPUT.format(
            instruction=example["instruction"],
            output=example["output"],
        )
    return text + eos_token


def load_config(config_path: str = "training/config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_dataset_from_jsonl(file_path: str, val_split: float = 0.05):
    """載入 JSONL 訓練集並切分驗證集。"""
    from datasets import Dataset

    records = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logger.info(f"載入 {len(records)} 筆訓練配對")
    dataset = Dataset.from_list(records)
    split = dataset.train_test_split(test_size=val_split, seed=42)
    return split["train"], split["test"]


def train(config_path: str = "training/config.yaml"):
    cfg = load_config(config_path)
    model_cfg = cfg["model"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]
    data_cfg = cfg["data"]

    # ── 嘗試載入 Unsloth（GPU 環境）────────────────────────────
    try:
        from unsloth import FastLanguageModel
        USE_UNSLOTH = True
        logger.info("使用 Unsloth 加速訓練")
    except ImportError:
        USE_UNSLOTH = False
        logger.warning("Unsloth 未安裝，使用原生 HuggingFace（較慢）")

    # ── 載入模型 ────────────────────────────────────────────────
    if USE_UNSLOTH:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_cfg["base"],
            max_seq_length=model_cfg["max_seq_length"],
            dtype=None,  # 自動選擇
            load_in_4bit=model_cfg["load_in_4bit"],
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_cfg["r"],
            target_modules=lora_cfg["target_modules"],
            lora_alpha=lora_cfg["lora_alpha"],
            lora_dropout=lora_cfg["lora_dropout"],
            bias=lora_cfg["bias"],
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16",
            bnb_4bit_use_double_quant=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_cfg["base"])
        model = AutoModelForCausalLM.from_pretrained(
            model_cfg["base"],
            quantization_config=bnb_config,
            device_map="auto",
        )
        model = prepare_model_for_kbit_training(model)
        peft_config = LoraConfig(
            r=lora_cfg["r"],
            lora_alpha=lora_cfg["lora_alpha"],
            target_modules=lora_cfg["target_modules"],
            lora_dropout=lora_cfg["lora_dropout"],
            bias=lora_cfg["bias"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)

    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── 載入資料集 ──────────────────────────────────────────────
    train_data, eval_data = load_dataset_from_jsonl(
        data_cfg["train_file"], val_split=data_cfg["val_split"]
    )

    eos_token = tokenizer.eos_token or ""

    def preprocess(examples):
        texts = [
            format_prompt(
                {
                    "instruction": i,
                    "input": inp,
                    "output": out,
                },
                eos_token=eos_token,
            )
            for i, inp, out in zip(
                examples["instruction"],
                examples["input"],
                examples["output"],
            )
        ]
        return tokenizer(
            texts,
            truncation=True,
            max_length=model_cfg["max_seq_length"],
            padding=False,
        )

    train_data = train_data.map(preprocess, batched=True, remove_columns=train_data.column_names)
    eval_data = eval_data.map(preprocess, batched=True, remove_columns=eval_data.column_names)

    # ── TRL SFTTrainer ──────────────────────────────────────────
    from trl import SFTTrainer, SFTConfig
    from transformers import DataCollatorForSeq2Seq

    sft_cfg = SFTConfig(
        output_dir=train_cfg["output_dir"],
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        per_device_eval_batch_size=train_cfg["per_device_eval_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        weight_decay=train_cfg["weight_decay"],
        warmup_ratio=train_cfg["warmup_ratio"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        optim=train_cfg["optim"],
        bf16=train_cfg["bf16"],
        fp16=train_cfg["fp16"],
        max_grad_norm=train_cfg["max_grad_norm"],
        logging_steps=train_cfg["logging_steps"],
        save_steps=train_cfg["save_steps"],
        eval_steps=train_cfg["eval_steps"],
        save_total_limit=train_cfg["save_total_limit"],
        evaluation_strategy=train_cfg["evaluation_strategy"],
        load_best_model_at_end=train_cfg["load_best_model_at_end"],
        report_to=train_cfg["report_to"],
        seed=train_cfg["seed"],
        max_seq_length=model_cfg["max_seq_length"],
        dataset_text_field=None,  # 已預處理
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_data,
        eval_dataset=eval_data,
        args=sft_cfg,
    )

    logger.info("開始訓練...")
    trainer.train()

    # ── 儲存模型 ────────────────────────────────────────────────
    output_dir = Path(train_cfg["output_dir"])
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    logger.info(f"模型已儲存至 {output_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="training/config.yaml")
    args = parser.parse_args()
    train(args.config)
