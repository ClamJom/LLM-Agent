from .BaseModel import BaseModel

import urllib3
import json
import copy

from typing import List
from urllib3 import request
import tools

urllib3.disable_warnings()


class OpenAi(BaseModel):
    """
    OpenAI模型
    ----------------
    :param url: 基础地址
    :param api_key: api_key
    :param model: 模型名称
    :param tempture: 温度，默认为0.7
    :param max_tokens: 最大token数，默认为1024
    :param top_p: 采样值，默认为1
    :param frequency_penalty: 频率惩罚，默认为0
    :param presence_penalty: 存在惩罚，默认为0
    """

    def __init__(self, url: str, api_key: str, model: str, **kwargs):
        """
        OpenAI模型
        ----------------
        :param url: 基础地址
        :param api_key: api_key
        :param model: 模型名称
        :param tempture: 温度，默认为0.7
        :param max_tokens: 最大token数，默认为1024
        :param top_p: 采样值，默认为1
        :param frequency_penalty: 频率惩罚，默认为0
        :param presence_penalty: 存在惩罚，默认为0
        :param enable_tools: 是否启用工具，默认为False
        :param stream: 是否流式输出，默认为False，当工具启用且工具数量不为0时，流式传输会被强制关闭
        :param stream_callback: 流式回调函数，默认为None
        """
        super().__init__()

        self.url = url
        self.api_key = api_key
        self.model = model
        self.tempture = kwargs.get("tempture", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 1024)
        self.top_p = kwargs.get("top_p", 1)
        self.frequency_penalty = kwargs.get("frequency_penalty", 0)
        self.presence_penalty = kwargs.get("presence_penalty", 0)
        self.system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")
        self.enable_tools = kwargs.get("enable_tools", False)
        self.tools = tools.get_tool_description() if self.enable_tools else []
        self.stream = kwargs.get("stream", False)
        if self.tools != []:
            # 不要在调用工具时使用流式传输
            self.stream = False
        self.stream_callback = kwargs.get("stream_callback", None)

        self.messages = []

        self.__headers = {
            "Authorization": "Bearer {}".format(self.api_key),
            "mj-api-secret": "{}".format(self.api_key),
            "Content-Type": "application/json",
        }

    def __parse(self, message: str):
        obj = json.loads(message)
        return obj["choices"][0]["message"]["content"]

    def __parse_stream(self, message: str):
        if not message:
            return ""
        obj = json.loads(message)
        if obj["choices"][0]["finish_reason"] == "stop":
            return ""
        if obj["choices"][0]["delta"].get("content") is None:
            return ""
        return obj["choices"][0]["delta"]["content"]

    def __call__(self, prompt: str | object, **kwargs) -> str:
        """
        调用模型
        -----------------
        :param prompt: 提示词（或对象，用于多模态）
        :param parse_message: 是否解析消息，默认为True
        :param stream: 是否流式输出，默认为False
        :param stream_callback: 流式回调函数，默认为None
        :return: 模型返回结果
        """
        if self.messages == [] and self.system_prompt != "":
            self.messages.append({"role": "system", "content": self.system_prompt})
        self.messages.append({"role": "user", "content": prompt})

        parse_message = kwargs.get("parse_message", True)
        answer = self.__request_main(parse_message)
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def __request_main(self, parse_message: bool = True):
        body = json.dumps(
            {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.tempture,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "stream": self.stream,
                "tools": None if self.tools == [] else self.tools,
            }
        )

        rsp = urllib3.request(
            "POST",
            self.url + "/chat/completions",
            headers=self.__headers,
            body=body,
            timeout=300,
            preload_content=False if self.stream else True,
        )

        if rsp.status != 200:
            return "Request Error:\n {}".format(rsp.reason)

        rsp_message = ""
        if self.stream:
            rsp_message = []
            for line in rsp.stream():
                line = line.decode("utf-8").strip()
                if line.startswith("data:"):
                    line = line[5:]
                    if line.find("[DONE]") != -1:
                        break
                    if parse_message:
                        rsp_message.append(copy.deepcopy(self.__parse_stream(line)))
                    else:
                        rsp_message.append(copy.deepcopy(line))
                    if self.stream_callback is not None:
                        self.stream_callback(rsp_message[-1])
            rsp_message = "".join(rsp_message)
        else:
            msg_obj = json.loads(rsp.data.decode("utf-8"))
            if self.enable_tools and self.__is_tools_calling(msg_obj):
                # 如果调用了工具，递归调用，返回最终结果
                self.messages.append(msg_obj["choices"][0]["message"])
                calling_results = self.__get_tools_calling(msg_obj)
                for tool_result in calling_results:
                    self.messages.append(tool_result)
                return self.__request_main(parse_message)
            if parse_message:
                rsp_message = msg_obj["choices"][0]["message"]["content"]
            else:
                rsp_message = rsp.data.decode("utf-8")
        return rsp_message

    def call_stream(self, prompt, parse_message: bool = True):
        if self.messages == [] and self.system_prompt != "":
            self.messages.append({"role": "system", "content": self.system_prompt})
        self.messages.append({"role": "user", "content": prompt})
        body = json.dumps(
            {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.tempture,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "stream": self.stream,
                "tools": None if self.tools == [] else self.tools,
            }
        )

        rsp = urllib3.request(
            "POST",
            self.url + "/chat/completions",
            headers=self.__headers,
            body=body,
            timeout=300,
            preload_content=False if self.stream else True,
        )

        if rsp.status != 200:
            return "Request Error:\n {}".format(rsp.reason)
        return rsp.stream()
        # rsp_message = []
        # for line in rsp.stream():
        # line = line.decode("utf-8").strip()
        # if line.startswith("data:"):
        #     line = line[5:]
        # if line.find("[DONE]") != -1:
        #     break
        # if parse_message:
        #     rsp_message.append(copy.deepcopy(self.__parse_stream(line)))
        # else:
        #     rsp_message.append(copy.deepcopy(line))
        # yield "{}\n".format(line)
        # "".join(rsp_message)
        # self.messages.append({"role":"assistant", "content": rsp_message})

    def __is_tools_calling(self, message: object):
        """
        判断是否为工具调用
        适用于可使用funciton calling的模型，如不支持请使用参数`enable_tools = False`
        """
        if not message or not self.enable_tools:
            return False
        if "tool_calls" not in message["choices"][0]["message"]:
            return False
        return True

    def __get_tools_calling(self, message: object):
        """
        获取工具调用
        适用于可使用funciton calling的模型，如不支持请使用参数`enable_tools = False`
        """
        if not message:
            return []
        tool_results = []
        if "tool_calls" not in message["choices"][0]["message"]:
            return tool_results
        for tool in message["choices"][0]["message"]["tool_calls"]:
            tool_name = tool["function"]["name"]
            tool_arg = json.loads(tool["function"]["arguments"])
            if type(tool_arg) == str:
                tool_arg = json.loads(tool_arg)
            tool_id = tool["id"]
            tool_results.append(
                {
                    "role": "tool",
                    "content": tools.call_tool_by_name(tool_name, **tool_arg),
                    "tool_call_id": tool_id,
                }
            )
        return tool_results

    def get_models(self):
        """
        获取模型列表
        """
        rsp = request("GET", self.url + "/models?type=text", headers=self.__headers)
        data = rsp.data.decode("utf-8")
        models = json.loads(data)["data"]
        model_list = [model["id"] for model in models]
        return model_list
