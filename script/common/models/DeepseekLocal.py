from .BaseModel import BaseModel

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Qwen2ForCausalLM,
    GenerationConfig,
)


class DeepseekLocal(BaseModel):
    """
    从本地加载Deepseek模型
    ---------------------
    :param path: 模型路径
    :param device: 设备
    :param tempture: 温度，默认为0.7
    :param max_tokens: 最大token数，默认为1024
    :param max_new_tokens: 最大新token数，默认为100
    :param frequency_penalty: 频率惩罚，默认为0
    :param presence_penalty: 出现惩罚，默认为0
    :param system_prompt: 系统提示
    """

    def __init__(self, path, **kwargs):
        """
        从本地加载Deepseek模型
        ---------------------
        :param path: 模型路径
        :param device: 设备
        :param tempture: 温度，默认为0.7
        :param max_tokens: 最大token数，默认为1024
        :param max_new_tokens: 最大新token数，默认为100
        :param frequency_penalty: 频率惩罚，默认为0
        :param presence_penalty: 出现惩罚，默认为0
        :param system_prompt: 系统提示
        """
        super().__init__()
        self.model_path = path
        self.device = kwargs.get("device", "cpu")
        self.tempture = kwargs.get("tempture", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 1024)
        self.max_new_tokens = kwargs.get("max_new_tokens", 100)
        self.system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model: Qwen2ForCausalLM = AutoModelForCausalLM.from_pretrained(
            self.model_path
        )

        if self.device == "cuda":
            self.model = self.model.to("cuda")

        self.messages = []

    def __call__(self, prompt: str, **kwargs):
        super().__call__(prompt, **kwargs)
        if self.messages == [] and self.system_prompt != "":
            self.messages.append({"role": "system", "content": self.system_prompt})
        self.messages.append({"role": "user", "content": prompt})

        input_tokens = self.tokenizer.apply_chat_template(
            self.messages, add_generation_prompt=True, return_tensors="pt"
        )
        old_tokens_length = input_tokens.shape[1]
        final_result = ""
        while True:
            output_tokens = self.model.generate(
                input_tokens,
                do_sample=True,
                temperature=self.tempture,
                max_new_tokens=self.max_new_tokens,
                top_p=1,
                top_k=0,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id,
            )
            if self.tokenizer.eos_token_id in output_tokens[0]:
                final_result = self.tokenizer.decode(
                    output_tokens[0, old_tokens_length:], skip_special_tokens=True
                )
                break
            input_tokens = output_tokens
        return final_result
