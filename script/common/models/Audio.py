import json

from io import BufferedReader
import requests

from .BaseModel import BaseModel


class AudioModel(BaseModel):
    """
    音频处理模型
    -----------------
    url: str, 模型地址
    api_key: str, API密钥
    model: str, 模型名称
    """

    def __init__(self, url, api_key, model):
        """
        音频处理模型
        -----------------
        url: str, 模型地址
        api_key: str, API密钥
        model: str, 模型名称
        """
        super().__init__()
        self.url = url
        self.api_key = api_key
        self.model = model

        self.__headers = {
            "Authorization": "Bearer {}".format(self.api_key),
            "mj-api-secret": "{}".format(self.api_key),
        }

    def __call__(self, file: BufferedReader):
        payload = {"model": self.model}
        files = [("file", (file.name, file))]
        rsp = requests.request(
            "POST",
            self.url + "/audio/transcriptions",
            headers=self.__headers,
            data=payload,
            files=files,
        )
        if rsp.status_code != 200:
            return "Error: Code{} Reason: {}".format(rsp.status_code, rsp.reason)
        return json.loads(rsp.text)["text"]
