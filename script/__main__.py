from common.models.OpenAi import OpenAi
from common.models.Audio import AudioModel
from setting.settings import *

import tools
import json
import do
import os
from pathlib import Path
from setting.prompt import get_system_prompt


class ImagePromptInitializer:
    def __init__(
        self,
        prompt: str,
    ):
        from urllib3 import request

        self.request = request
        self.prompt = prompt
        self.images = []

    def __to_base_64(self, image_url: str, is_url=False):
        import base64

        if is_url:
            rsp = self.request("GET", image_url)
            return base64.b64encode(rsp.data).decode("utf-8")
        else:
            with open(image_url, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    def add(self, image_url: str, is_url=False):
        if is_url:
            self.images.append({"type": "image_url", "image_url": image_url})
        else:
            self.images.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{self.__to_base_64(image_url, is_url)}"
                    },
                }
            )

    def __call__(self):
        content = (
            [{"type": "text", "text": self.prompt}]
            if self.images == []
            else self.prompt
        )
        for image in self.images:
            content.append(image)
        return content


class StreamHandler:
    def __init__(self):
        import sys

        self.__sys = sys
        self.value = ""

    def __call__(self, message):
        self.__sys.stdout.write(message)
        self.__sys.stdout.flush()
        self.value += message

    def clear(self):
        self.value = ""


def parse_message(message: str):
    message = message.split("```json")[1].split("```")[0]
    return json.loads(message)


def main():
    # 无前端的测试代码
    system_prompt = get_system_prompt()
    model = OpenAi(
        url=API_URL,
        api_key=API_KEY,
        model="Qwen/Qwen2.5-32B-Instruct",
        enable_tools=False,
        system_prompt=system_prompt,
    )
    # 使用LM-Studio在本地启动模型时可以使用以下代码，API_KEY可以留空
    # model = OpenAi(url="http://localhost:1234/v1", api_key=API_KEY,
    #                 model="qwen2.5-7b-instruct-1m",
    #                 enable_tools = False,
    #                 system_prompt=system_prompt)
    prompts = [
        "由于骨折需要拆线，我要请明天后天两天的假前往医院复诊，请帮我填写一个请假单",
        "我想学习Python，有什么好的链接吗？",
    ]
    for prompt in prompts:
        rsp = model(prompt)
        data = parse_message(rsp)
        while "tools" in data and data["tools"] != []:
            results = []
            for tool_calling in data["tools"]:
                tool_name = tool_calling["name"]
                tool_arg = tool_calling["args"]
                if type(tool_arg) == str:
                    tool_arg = json.loads(tool_arg)
                result = tools.call_tool_by_name(tool_name, **tool_arg)
                results.append({"name": tool_name, "result": str(result)})
            rsp = model(str(results))
            data = parse_message(rsp)
    Path("./data").mkdir(parents=True, exist_ok=True)
    with open("./data/result.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(model.messages, ensure_ascii=False))


def web():
    # 带前端的Web代码
    import uvicorn

    do.init_database()
    uvicorn.run("web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    web()
    # import rag

    # _rag = rag.RAG("tb1.txt")
    # for rsp in _rag.init():
    #     obj = json.loads(rsp)
    #     idx, total = obj["idx"], obj["total"]
    #     print(f"{idx} / {total}")

    # _rag = rag.RAG("tb3.txt")
    # # _rag.file_name = "tb3.txt"
    # for rsp in _rag.init():
    #     obj = json.loads(rsp)
    #     idx, total = obj["idx"], obj["total"]
    #     print(f"{idx} / {total}")
    # result = _rag.search("程心的身世")
    # print(result)
