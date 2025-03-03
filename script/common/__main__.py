from models import OpenAi


class StreamHandler:
    def __init__(self):
        import sys

        self.__sys = sys
        self.value = ""

    def __call__(self, message):
        self.__sys.stdout.write(message)
        self.__sys.stdout.flush()
        self.value += message


if __name__ == "__main__":
    model = OpenAi.OpenAi(
        url="https://api.siliconflow.cn/v1",
        api_key="sk-tpotoeoqmziohjokjrnejqerehlqfpkapsuoiigoonjsomav",
        model="deepseek-r1-distill-qwen-1.5b",
    )
    model("你好", stream=True, stream_callback=StreamHandler())
