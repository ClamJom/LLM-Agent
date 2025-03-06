import os
import json
import tools
import do
from rag import RAG
from setting import prompt
from datetime import datetime
from pathlib import Path
from common.models import OpenAi, Audio
from common import systemInfo
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, Body
from setting.settings import *
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        content = [{"type": "text", "text": self.prompt}]
        for image in self.images:
            content.append(image)
        return content


class ChatRequest(BaseModel):
    model: str
    prompt: str
    message_list: list[dict]
    attachments: list[dict] = []
    settings: dict

    def attachment_handler(self):
        results = []
        for attachment in self.attachments:
            if str(attachment["type"]).find("image") != -1:
                model = OpenAi.OpenAi(API_URL, API_KEY, IMAGE_HANDLER)
                model.system_prompt = prompt.IMAGE_PROMPT
                image_prompt = ImagePromptInitializer(self.prompt)
                image_prompt.add(os.path.join(UPLOAD_PATH, attachment["name"]))
                res = model(image_prompt())
                results.append({"type": "image", "result": res})
            elif str(attachment["type"]).find("text") != -1:
                content = ""
                with open(
                    os.path.join(UPLOAD_PATH, attachment["name"]), "r", encoding="utf-8"
                ) as f:
                    content = f.read()
                    f.close()
                model = OpenAi.OpenAi(API_URL, API_KEY, TEXT_HANDLER)
                model.system_prompt = prompt.TEXT_PROMPT
                res = model(content)
                results.append({"type": "text", "result": res})
            elif str(attachment["type"]).find("audio") != -1:
                model = Audio.AudioModel(API_URL, API_KEY, VOICE_HANDLER)
                with open(os.path.join(UPLOAD_PATH, attachment["name"]), "rb") as f:
                    res = model(f)
                    results.append({"type": "audio", "result": res})
            else:
                # 处理其它文件，如音频、Word文档、视频、Excel等
                pass
        return results


class ToolRequest(BaseModel):
    tools: list[dict] = []

    def get_tools_result(self):
        results = []
        for tool_calling in self.tools:
            tool_name = tool_calling["name"]
            if "args" not in tool_calling:
                tool_arg = {}
            else:
                tool_arg = tool_calling["args"]
            if type(tool_arg) == str:
                tool_arg = json.loads(tool_arg)
            result = tools.call_tool_by_name(tool_name, **tool_arg)
            results.append({"name": tool_name, "result": str(result)})
        return results


def get_default_settings():
    system_prompt = prompt.get_system_prompt()
    return {
        "system_prompt": system_prompt,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 2048,
        "presence_penalty": 0,
        "stream": True,
    }


def UUID():
    import uuid

    return str(uuid.uuid4())


@app.get("/")
def index():
    return "Hello, World"


@app.get("/system_info")
def get_system_info():
    system_info = {}
    system_info["cpu"] = systemInfo.GetCpuInfo()
    system_info["memery"] = systemInfo.GetMemInfo()
    return system_info

@app.get("/models")
def get_models():
    return OpenAi.OpenAi(API_URL, API_KEY, DEFAULT_MODEL).get_models()


@app.get("/default_model")
def get_default_model():
    return DEFAULT_MODEL


@app.post("/tools")
def tools_result(toolRequest: ToolRequest):
    try:
        return json.dumps(toolRequest.get_tools_result())
    except Exception as e:
        return json.dumps(
            [{"name": "error", "result": "工具调用出错，请检查参数与格式"}]
        )


@app.get("/conversations")
def get_conversations():
    return do.get_conversations()


@app.post("/new/conversation")
def start_new_conversation(
    title: str = Body(..., title="title", embed=True, description="标题")
):
    return do.insert_conversation(title, datetime.now())


@app.post("/save/conversation")
def save_conversation(
    conversation_id: str = Body(
        ..., title="conversation_id", embed=True, description="会话ID"
    ),
    messages: list[dict] = Body(
        ..., title="messages", embed=True, description="消息列表"
    ),
):
    do.update_messages(conversation_id, messages)
    return do.get_messages(conversation_id)


@app.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    return do.get_messages(conversation_id)


@app.post("/update/conversation")
def update_conversation(
    conversation_id: str = Body(
        ..., title="conversation_id", embed=True, description="会话ID"
    ),
    messages: list[dict] = Body(
        ..., title="messages", embed=True, description="消息列表"
    ),
):
    do.update_messages(conversation_id, messages)


@app.get("/delete/conversation/{conversation_id}")
def delete_conversation(conversation_id: str):
    do.delete_conversation(conversation_id)


@app.post("/title")
def get_title(messages: list[dict]):
    title_summerizer_settings = {"stream": True, "system_prompt": prompt.TITLE_PROMPT}
    model = OpenAi.OpenAi(
        API_URL, API_KEY, TITLE_SUMMERIZER, **title_summerizer_settings
    )
    _prompt = "对话内容:{}".format(messages)
    return StreamingResponse(model.call_stream(_prompt), media_type="text/event-stream")


@app.post("/chat")
def chat(chatRequest: ChatRequest):
    model = OpenAi.OpenAi(API_URL, API_KEY, chatRequest.model, **chatRequest.settings)
    model.messages = chatRequest.message_list
    attach_result = chatRequest.attachment_handler()
    _prompt = chatRequest.prompt
    if attach_result != []:
        _prompt += "附件：\n"
        for result in attach_result:
            if result["type"] == "image":
                _prompt += "一张图片，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "text":
                _prompt += "一个文本文件，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "audio":
                _prompt += "一个音频文件，内容如下：\n{}\n".format(result["result"])
    response = model(_prompt)
    return response


@app.post("/sse/chat")
async def char_stream(chatRequest: ChatRequest):
    model = OpenAi.OpenAi(API_URL, API_KEY, chatRequest.model, **chatRequest.settings)
    model.messages = chatRequest.message_list
    attach_result = chatRequest.attachment_handler()
    _prompt = chatRequest.prompt
    if attach_result != []:
        _prompt += "附件：\n"
        for result in attach_result:
            if result["type"] == "image":
                _prompt += "一张图片，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "text":
                _prompt += "一个文本文件，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "audio":
                _prompt += "一个音频文件，内容如下：\n{}\n".format(result["result"])
    return StreamingResponse(model.call_stream(_prompt), media_type="text/event-stream")


@app.get("/default_settings")
def get_settings():
    return get_default_settings()


@app.post("/upload_file")
async def upload_file(upload_file: UploadFile):
    ext_name = os.path.splitext(upload_file.filename)[1]
    uuid = UUID()
    file_name = "{}{}".format(uuid, ext_name)
    content = await upload_file.read()
    file_path = os.path.join(UPLOAD_PATH, file_name)
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(file_path):
        os.remove(file_path)
    with open(file_path, "wb") as f:
        f.write(content)
    return file_name


@app.get("/download_file/{file_name}")
async def download_file(file_name: str):
    file_path = os.path.join(UPLOAD_PATH, file_name)
    if not os.path.exists(file_path):
        return {"error": "文件不存在"}
    return StreamingResponse(
        open(file_path, "rb"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename={}".format(file_name)},
    )

@app.get("/rag/supported_file_types")
async def get_supported_file_types():
    return ".txt"

@app.get("/rag/file_list")
def get_rag_files():
    import glob
    rag_upload_path = os.path.join(UPLOAD_PATH, "rag")
    if not os.path.exists(rag_upload_path):
        os.makedirs(rag_upload_path)
    file_full_path_list = glob.glob(os.path.join(rag_upload_path, "*.*"))
    file_list = [os.path.basename(file_full_path) for file_full_path in file_full_path_list]
    return file_list

@app.post("/rag/upload_file")
async def upload_rag_file(upload_file: UploadFile):
    file_name = upload_file.filename
    rag_upload_path = os.path.join(UPLOAD_PATH, "rag")
    if not os.path.exists(rag_upload_path):
        os.makedirs(rag_upload_path)
    rag = RAG(file_name)
    file_path = os.path.join(rag_upload_path, file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        rag.delete_file_data(file_name)
    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 流式返回文件处理进度
    return EventSourceResponse(rag.init())

@app.get("/rag/test")
async def rag_test():
    import time
    def foo():
        for i in range(100):
            yield json.dumps({"step": i}) + "\n"
            time.sleep(0.5)
    return EventSourceResponse(foo())

@app.delete("/rag/delete_file/{file_name}")
async def rag_delete_file(file_name: str):
    rag = RAG("")
    rag.delete_file_data(file_name)
    if os.path.exists(os.path.join(RAG_UPLOAD_PATH, file_name)):
        os.remove(os.path.join(RAG_UPLOAD_PATH, file_name))
    return "OK"

@app.get("/rag/default_settings")
async def rag_get_settings():
    return {
        "temperature": 0.1,
        "top_k": 4,
        "system_prompt": prompt.RAG_PROMPT,
        "model": DEFAULT_MODEL
    }

@app.get("/rag/relatives")
async def get_relatives(query: str, top_k: int = 4):
    rag = RAG("")
    rag_result = rag.search(query, top_k)
    search_list = []
    cmap = {}
    for idx, doc in enumerate(rag_result["documents"][0]):
        file_name = rag_result["metadatas"][0][idx]["file_name"]
        start_line = rag_result["metadatas"][0][idx]["start_line"]
        end_line = rag_result["metadatas"][0][idx]["end_line"]
        dis = rag_result["distances"][0][idx]
        if dis > 0.3:
            continue
        unique = "{}{}{}".format(file_name, start_line, end_line)
        if unique in cmap:
            continue
        else:
            cmap[unique] = True
        search_list.append({
            "file_name": file_name,
            "start": start_line,
            "end": end_line,
            "context": doc,
            "relative": 1 - dis
        })
    return search_list

@app.post("/rag/chat")
async def rag_chat(chatRequest: ChatRequest):
    # 默认为SSE
    model = OpenAi.OpenAi(API_URL, API_KEY, chatRequest.model, **chatRequest.settings)
    model.messages = chatRequest.message_list
    attach_result = chatRequest.attachment_handler()
    _prompt = chatRequest.prompt
    if attach_result != []:
        _prompt += "附件：\n"
        for result in attach_result:
            if result["type"] == "image":
                _prompt += "一张图片，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "text":
                _prompt += "一个文本文件，内容如下：\n{}\n".format(result["result"])
            elif result["type"] == "audio":
                _prompt += "一个音频文件，内容如下：\n{}\n".format(result["result"])
    # 处理RAG
    top_k = chatRequest.settings["top_k"] if "top_k" in chatRequest.settings else 4
    rag = RAG("")   # 只处理搜索时不用文件名，也不必初始化
    rag_result = rag.search(_prompt, top_k)
    result_num = len(rag_result["documents"][0])
    rag_prompt = chatRequest.settings["system_prompt"]
    if result_num != 0:
        rag_prompt += "参考文档：\n"
    cmap = {}
    for idx, doc in enumerate(rag_result["documents"][0]):
        file_name = rag_result["metadatas"][0][idx]["file_name"]
        start_line = rag_result["metadatas"][0][idx]["start_line"]
        end_line = rag_result["metadatas"][0][idx]["end_line"]
        dis = rag_result["distances"][0][idx]
        if dis > 0.26:
            continue
        unique = "{}{}{}".format(file_name, start_line, end_line)
        if unique in cmap:
            continue
        else:
            cmap[unique] = True
        rag_prompt += "文件名：{}\n".format(file_name)
        rag_prompt += "开始行数：{}\n".format(start_line)
        rag_prompt += "结束行数：{}\n".format(end_line)
        rag_prompt += "相关度：{}\n".format(1 - dis)
        rag_prompt += "内容：\n{}\n\n".format(doc)
    if chatRequest.message_list != []:
        for idx in range(len(model.messages)):
            if model.messages[idx]["role"] == "system":
                model.messages[idx]["content"] = rag_prompt
                break
    else:
        model.system_prompt = rag_prompt
    return StreamingResponse(model.call_stream(rag_prompt), media_type="text/event-stream")