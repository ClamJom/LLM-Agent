<script>
import axios from 'axios';
import { MdPreview, MdEditor } from 'md-editor-v3';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import 'md-editor-v3/lib/style.css'

/**
 * 等待重构
 */

export default {
  components: {
    MdPreview, MdEditor
  },
  data() {
    return {
      models: [],
      model: "Qwen/Qwen2.5-32B-Instruct",
      currentConversationID: "",
      title: "",
      messages: [],
      attachments: [],
      conversationList: [],
      generating: false,
      message: "",
      settings: {
        system_prompt: "",
        temperature: 0.7,
        top_p: 0.9,
        max_tokens: 2048,
        presence_penalty: 0,
        stream: true
      },
      abortSignal: null,
      dialogToggle: {
        system_prompt: false
      }
    }
  },
  methods: {
    async getDefaultSettings() {
      const res = await axios.get("/api/default_settings");
      this.settings = res.data;
    },
    async getModels() {
      const res = await axios.get("/api/models");
      this.models = res.data;
    },
    async getDefaultModel() {
      const res = await axios.get("/api/default_model");
      this.model = res.data;
    },
    async getConversationList() {
      const res = await axios.get("/api/conversations");
      this.conversationList = res.data.reverse();
    },
    async initData() {
      await this.getDefaultSettings();
      await this.getModels();
      await this.getDefaultModel();
      await this.getConversationList();
    },
    getTitle() {
      if (this.messages.length < 2 || this.title !== "") return;
      const self = this;
      self.title = "";
      let messageFilter = self.messages.filter((item) => { return item["role"] !== "system" });
      let abortSignal = new AbortController();
      fetchEventSource("/api/title", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        signal: abortSignal.signal,
        body: JSON.stringify(messageFilter),
        onmessage: (msg) => {
          if (msg.data === "[DONE]") {
            abortSignal.abort();
            return;
          }
          let data = JSON.parse(msg.data);
          if (data["choices"][0]["finish_reason"] == "stop" ||
            data["choices"][0]["delta"]["content"] === undefined) {
            abortSignal.abort();
          }
          const token = data["choices"][0]["delta"]["content"];
          self.title += token;
        }
      }).then(() => {
        self.startNewConversation();
      })
    },
    handleInputKeyDown(e){
      if(!e.shiftKey && e.keyCode === 13){
        e.preventDefault();
        this.sendMessage();
      }
    },
    sendMessage() {
      if (this.generating) {
        return;
      }
      if (this.message === "") {
        alert("消息不能为空！");
        return;
      }
      const prompt = this.message;
      this.message = "";
      this.generating = true;
      this.abortSignal = new AbortController();
      const data = {
        "prompt": prompt,
        "model": this.model,
        "attachments": [...this.attachments],
        "settings": JSON.parse(JSON.stringify(this.settings)),
      }
      // 历史消息列表
      data["message_list"] = [];
      for (let message of this.messages) {
        let item = { "role": message["role"], "content": message["content"] };
        // 由于模型只支持"system"、""user"和"assistant"，故需要转换
        // 只有部分模型支持"tool"角色，采用System-Prompt型时，兼顾通用性将其转换为"user"
        // 为了渲染，将模型调用的模型对话角色定义"tool_invoker"，这里将其转回"assistant"
        if (item["role"] === "tool") {
          item["role"] = "user";
          item["content"] = JSON.stringify({ "from": "tool", "content": item["content"] });
        } else if (item["role"] === "tool_invoker") {
          item["role"] = "assistant";
        } else if (item["role"] === "user") {
          item["content"] = JSON.stringify({
            "from": "user",
            "content": item["content"],
          });
        }
        data["message_list"].push(item);
      }
      // 如果消息列表为空，则添加系统提示
      if (this.messages.length === 0) {
        this.messages.push({
          "role": "system",
          "content": this.settings.system_prompt,
          "timestamp": new Date().getTime()
        });
      }
      // 必要时，将新消息推至消息渲染列表
      if (this.messages.length > 0 && this.messages[this.messages.length - 1].role !== "tool") {
        let tempUserMessage = {
          "role": "user",
          "content": prompt,
          "timestamp": new Date().getTime()
        };
        if (this.attachments.length > 0) {
          tempUserMessage.attachments = this.attachments;
          this.attachments = [];
        }
        this.messages.push(tempUserMessage);
      } else if (this.messages == 0) {
        let tempUserMessage = {
          "role": "user",
          "content": prompt,
          "timestamp": new Date().getTime()
        };
        if (this.attachments.length > 0) {
          tempUserMessage.attachments = this.attachments;
        }
        this.messages.push(tempUserMessage);
      }
      // 创建助手回复消息，当助手回复时，更新其中的内容
      this.messages.push({
        "role": "assistant",
        "content": "",
        "timestamp": new Date().getTime()
      });
      if (this.settings.stream) {
        // 流式传输处理
        this.SSEFetch("/api/sse/chat", data);
      } else {
        axios.post("/api/chat", data).then(res => {
          this.messages[this.messages.length - 1].content += res.data;
          this.generating = false;
          this.abortSignal = null;
        });
      }
    },
    startNewConversation() {
      axios.post("/api/new/conversation", {
        title: this.title
      }).then(res => {
        this.currentConversationID = res.data;
        if(!this.generating){
          this.saveConversation();
        }
      });
    },
    saveConversation() {
      axios.post("/api/save/conversation", {
        conversation_id: String(this.currentConversationID),
        messages: this.messages
      }).then((res) => {
        // this.messages = JSON.stringify(res);
        this.getConversationList();
        // this.getConversation();
      });
    },
    getConversation() {
      axios.get("/api/conversation/" + this.currentConversationID).then(res => {
        this.messages = res.data;
      });
    },
    getMessages() {
      axios.get("/api/conversation/" + this.currentConversationID).then(res => {
        // this.messages = res.data;
        const data = res.data;
        data.forEach((item) => {
          let attachments = item["attachments"];
          item["attachments"] = JSON.parse(attachments.replaceAll("'", "\""));
        });
        this.messages = data;
        setTimeout(this.scrollChatBoxToBottom, 500);
      });
    },
    updateConversationList() {
      axios.post("/api/update/conversation", {
        conversation_id: String(this.currentConversationID),
        messages: this.messages
      }).then(() => { });
    },
    conversationNameClickHandler(conversationID) {
      this.currentConversationID = conversationID;
      this.getConversationList();
      this.conversationList.forEach((item) => {
        if (item[0] === conversationID) {
          this.title = item[1];
        }
      });
      this.getMessages();
    },
    deleteConversation(conversationID) {
      this.conversationList = this.conversationList.filter((item) => {
        return item[0] !== conversationID;
      });
      axios.get("/api/delete/conversation/" + conversationID).then(() => { })
      if (conversationID === this.currentConversationID) {
        this.currentConversationID = "";
        this.title = "";
        this.messages = [];
      }
    },
    newConversationHandler() {
      this.getConversationList();
      this.currentConversationID = "";
      this.messages = [];
      this.title = "";
    },
    scrollChatBoxToBottom(){
      const clientHeight = this.$refs.chat_container.clientHeight;
      const scrollHeight = this.$refs.chat_container.scrollHeight;
      const scrollTop = this.$refs.chat_container.scrollTop;
      if(scrollTop + clientHeight >= scrollHeight) return;
      this.$refs.chat_container.scrollTo({
        top: scrollHeight - clientHeight,
        behavior: "smooth",
      });
    },
    SSEFetch(url, data) {
      // 专用于消息的流式传输处理
      const self = this;
      let thinking = "";
      let thinkOver = false;
      fetchEventSource(url, {
        method: "POST",
        headers: {
          "Content-Type": 'application/json',
        },
        signal: this.abortSignal.signal,
        body: JSON.stringify(data),
        onmessage: (msg) => {
          if (msg.data === "[DONE]") {
            // 流传输终止信号
            self.generating = false;
            return;
          }
          let data = JSON.parse(msg.data);
          if (data["choices"][0]["finish_reason"] == "stop") {
            // 流传输终止信号
            this.generating = false;
            return;
          }
          if (data["choices"][0]["delta"]["content"] === undefined) {
            // 回复的结构不是标准结构说明传输已经完成
            return;
          }
          if (data["choices"][0]["delta"]["content"] === null) {
            // 模型是推理型的，带有reasoning_content，解析reasoning_content
            let token = data["choices"][0]["delta"]["reasoning_content"];
            if (self.messages[self.messages.length - 1].content === "") {
              self.messages[self.messages.length - 1].content = "<div class='thinking'>";
            }
            thinking += token;
            self.messages[self.messages.length - 1].content += token;
          } else {
            // 当模型是生成型的，直接解析token。也可能是推理模型已经思考完成，处理其回复的内容
            if (!thinkOver) {
              self.messages[self.messages.length - 1].content += "</div>\n\n";
              thinkOver = true;
            }
            let token = data["choices"][0]["delta"]["content"];
            self.messages[self.messages.length - 1].content += token;
          }
          self.scrollChatBoxToBottom();
        },
        onerror(err) {
          console.log(err);
          throw err;
        },
        onclose() {
          let rsp = self.messages[self.messages.length - 1].content;
          if (thinking !== "") {
            thinking = "<div class='thinking'>" + thinking + "</div>\n\n";
          }
          self.messages[self.messages.length - 1].content = thinking + self.parseMyJson(rsp);
          // self.messages[self.messages.length - 1].content = thinking + rsp;
          if (self.messages.length > 2) self.getTitle();
          self.abortSignal = null;
        }
      }).then(()=>{
        if (self.currentConversationID !== "") {
          // 保存对话
          self.updateConversationList();
        }else{
          this.saveConversation();
        }
      });
    },
    parseMyJson(rsp) {
      // 解析回答，用于自定义结构体解析与工具调用
      let compareRsp = rsp;
      const self = this;
      compareRsp = compareRsp.replace("```json", "");
      if (rsp === compareRsp) {
        return rsp;
      } else {
        rsp = rsp.split("```json")[1].split("```")[0];
      }
      const obj = JSON.parse(rsp);
      if (obj["tools"] !== undefined && obj["tools"].length > 0) {
        self.generating = false;
        // self.messages = self.messages.slice(0, self.messages.length - 1);
        // self.messages[self.messages.length - 1].role = "tool_invoker";
        self.tools_invoke(obj["tools"]);
        return obj["conversation"];
      }
      return obj["conversation"];
    },
    cancelGenerate() {
      // 终止生成
      if (this.abortSignal !== null) {
        this.abortSignal.abort();
        this.generating = false;
      }
    },
    reanswer() {
      // 重新回答
      let lastPrompt = "";
      let lastPromptIndex = 0;
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === "user") {
          lastPrompt = this.messages[i].content;
          lastPromptIndex = i;
          break;
        }
      }
      this.messages = this.messages.slice(0, lastPromptIndex);
      this.message = lastPrompt;
      this.sendMessage();
    },
    tools_invoke(tools) {
      // 调用工具
      axios.post("/api/tools", {
        tools
      }).then((rsp) => {
        this.messages.push({
          "role": "tool",
          "content": rsp.data,
          "timestamp": new Date().getTime(),
        });
        this.message = "Tool Request";
        this.sendMessage();
      });
    },
    upload_file() {
      const uploadEle = this.$refs["uploadEle"];
      const file = uploadEle.files[0];
      if (file === undefined) {
        return;
      }
      const type = file.type;
      const data = new FormData();
      data.append("upload_file", file);
      axios.post("/api/upload_file", data).then((rsp) => {
        this.attachments.push({
          type: type,
          name: rsp.data
        });
      });
    }
  },
  created() {
    this.initData();
  }
}
</script>

<template>
  <div class="main_container">
    <div class="left_bar">
      <!-- 左边栏，放置模型选择、对话记录、模型设置 -->
      <div class="model_settings">
        <div class="setting_item">
          <div class="model_selector">
            <div class="setting_name">模型：</div>
            <div class="setting_value">
              <select name="model" id="model" v-model="model">
                <option v-for="(model, idx) of models" :value="model" :key="idx">{{ model }}</option>
              </select>
            </div>
          </div>
        </div>
        <div class="setting_item system_prompt">
          <div class="setting_name">系统提示词</div>
          <div class="setting_value">
            <dialog :open="dialogToggle.system_prompt" style="z-index:1000; max-width: 90vw;">
              <div class="system_prompt_setting">
                <MdEditor v-model="settings.system_prompt"></MdEditor>
              </div>
              <div class="dialog_close">
                <button @click="dialogToggle.system_prompt = false">确认</button>
              </div>
            </dialog>
            <div v-if="!dialogToggle.system_prompt">
              <textarea name="system_prompt" v-model="settings.system_prompt" readonly
                style="resize: none; width: calc(100% - 10px)" rows="5" @click="dialogToggle.system_prompt = true">
              </textarea>
            </div>
          </div>
        </div>
        <div class="setting_item">
          <div class="setting_name">对话记录：</div>
          <div class="conversation_list">
            <div class="conversation_item">
              <div class="conversation_name" @click="newConversationHandler">开始新对话</div>
            </div>
            <div class="conversation_item" v-for="(conversation, idx) of conversationList" :key="idx">
              <div class="conversation_name" @click="conversationNameClickHandler(conversation[0])">
                {{ conversation[1] }}
              </div>
              <div class="conversation_delete" @click="deleteConversation(conversation[0])">X</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="body">
      <!-- 主体部分 -->
      <div class="chat_title">
        <h3 v-if="title !== ''">{{ title }}</h3>
        <h3 v-else>新对话</h3>
      </div>
      <div class="chat_container" ref="chat_container">
        <!-- 聊天记录 -->
        <TransitionGroup name="message_fade_in">
          <div class="message" v-for="(message, m_idx) of messages" :key="m_idx" :class="{
            'user_message': message.role == 'user',
            'assistant_message': message.role == 'assistant',
            'tool_message': message.role == 'tool'
          }">
            <div class="message_header" v-if="message.role !== 'system' && message.role !== 'tool'">
              {{ new Date(parseInt(message.timestamp)).toLocaleString() }}
            </div>
            <div class="message_main" v-if="message.role === 'user' || message.role === 'assistant'">
              <div class="message_content">
                <MdPreview v-if="message.content != ''" v-model="message.content" :code-foldable="false"></MdPreview>
                <div v-else>生成中......</div>
              </div>
              <div class="message_foot">
                <div class="reanswer" v-if="message.role === 'assistant'">
                  <button @click="reanswer" style="font-size: x-small;">重新回答</button>
                </div>
                <div class="attachment" v-if="message.role === 'user' && message.attachments">
                  <div class="attachment_list">
                    <div class="attachment_item" v-for="(attach, idx) of message.attachments" :key="idx">
                      <!-- 预览附件 -->
                      <div class="attachment_name">
                        <img v-if="attach.type.indexOf('image') !== -1" :src="'/api/download_file/' + attach.name"
                          :alt="attach.name" class="preview_img">
                        <span v-else>{{ attach.name }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="message_main tool" v-else-if="message.role === 'tool'">
              <div class="tool_title">使用了以下工具：</div>
              <div class="tool_box" v-for="(tool, idx) of JSON.parse(message.content)" :key="idx">
                <div class="tool_name_item">工具名：{{ tool["name"] }}</div>
                <div class="tool_result_item">结果: {{ tool["result"] }}</div>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </div>
      <div class="message_send_box">
        <div class="message_send_header">
          <!-- 文件上传及其预览 -->
          <div class="attachment">
            <div class="upload_file">
              <label for="upload_file">上传文件</label>
              <input type="file" @change="upload_file" ref="uploadEle" style="display: none;" id="upload_file" multiple>
            </div>
            <div class="attachment_list">
              <div class="attachment_item" v-for="(attach, idx) of attachments" :key="idx">
                <!-- 预览附件 -->
                <div class="attachment_name"
                  @click="attachments = attachments.filter((item) => item.name !== attach.name)">
                  <img v-if="attach.type.indexOf('image') !== -1" :src="'/api/download_file/' + attach.name"
                    :alt="attach.name" class="preview_img">
                  <span v-else>{{ attach.name }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="clear_messages">
            <button @click="messages = []">清空当前聊天</button>
          </div>
          <div class="abort_generate" v-if="generating">
            <button @click="cancelGenerate">停止生成</button>
          </div>
        </div>
        <div class="message_send_body">
          <!-- 消息发送框 -->
          <textarea name="send_message" id="send_message" placeholder="请输入消息....." class="input_message"
            v-model="message" @keydown="handleInputKeyDown">
            </textarea>
        </div>
        <div class="message_send_foot" :class="{ generating }">
          <!-- 发送按钮 -->
          <div v-if="!generating" @click="sendMessage">发送</div>
          <div v-else class="generating">生成中</div>
        </div>
      </div>
    </div>
    <div class="right_bar"></div>
  </div>
</template>

<style scoped>
@media screen and (max-width: 768px) {
  .main_container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .left_bar {
    position: absolute;
    width: 100%;
    height: 100px;
    top: 0;
    left: 0;
    padding: 0;
    margin: 0;
    border-bottom: 1px solid grey;
  }

  .model_selector {
    position: relative;
    width: 200px;
    height: fit-content;
  }

  .model_selector select {
    position: relative;
    width: 100%;
  }

  .body {
    position: absolute;
    width: 100%;
    height: calc(100% - 100px);
    top: 100px;
    left: 0;
  }
}

@media screen and (min-width: 768px) {
  .main_container {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .left_bar {
    position: absolute;
    left: 0;
    top: 0;
    width: 200px;
    height: 100%;
  }

  .model_selector {
    position: relative;
    width: calc(100% - 5px);
    height: fit-content;
  }

  .model_selector select {
    position: relative;
    width: 100%;
  }

  .model_settings {
    position: absolute;
    max-height: calc(100% - 200px);
    width: calc(100% - 5px);
  }

  .model_settings .setting_item {
    position: relative;
    width: 100%;
    max-height: 100%;
    margin-bottom: 5px;
  }

  .dialog_close {
    position: relative;
    width: 100%;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: end;
  }

  .dialog_close button {
    position: relative;
    outline: none;
  }

  .conversation_list {
    position: relative;
    padding-left: 5px;
    max-height: 220px;
    overflow-y: auto;
  }

  .conversation_item {
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .conversation_name {
    position: relative;
    text-wrap: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    color: rgb(82, 95, 80);
    cursor: pointer;
    transition: all 0.5s;
  }

  .conversation_name:hover {
    color: rgb(76, 255, 85);
  }

  .conversation_delete {
    position: relative;
    cursor: pointer;
    transition: all 0.5s;
    padding-left: 5px;
  }

  .conversation_delete:hover {
    color: rgb(255, 0, 0);
  }

  .body {
    position: absolute;
    width: calc(100% - 200px);
    height: 100%;
    top: 0;
    left: 200px;
    border-left: 1px solid grey;
  }

  .chat_title {
    position: sticky;
    background-color: white;
    top: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    width: 100%;
    height: fit-content;
    z-index: 100;
  }

  .chat_title h3 {
    margin: 0;
    padding: 0;
  }

  .chat_container {
    position: absolute;
    top: 25px;
    width: 100%;
    height: calc(100% - 225px);
    overflow-y: auto;
    padding: 5px;
    box-sizing: border-box;
  }

  .message {
    position: relative;
    width: 100%;
    display: flex;
    box-sizing: border-box;
    margin-bottom: 5px;
    padding-top: 10px;
    flex-direction: column;
    align-items: center;
  }

  .message_header {
    position: relative;
    font-size: smaller;
    margin-bottom: 5px;
    color: grey;
  }

  .user_message {
    justify-content: end;
  }

  .message_main {
    position: relative;
    padding: 10px;
    margin-right: 10px;
    opacity: 1;
    width: fit-content;
    max-width: calc(100% - 30px);
  }

  .user_message .message_main {
    background-color: rgb(32, 187, 122);
    border-radius: 10px;
    align-self: flex-end;
  }

  .user_message .md-editor-previewOnly {
    background-color: rgb(32, 187, 122);
  }

  .user_message .message_main::after {
    content: "";
    position: absolute;
    display: block;
    width: 0;
    height: 0;
    border-left: 10px solid rgb(32, 187, 122);
    border-top: 2px solid transparent;
    border-bottom: 10px solid transparent;
    top: 10px;
    right: -10px;
  }

  .assistant_message .message_main {
    background-color: rgb(214, 214, 214);
    border-radius: 10px;
    margin-left: 10px;
    align-self: flex-start;
  }

  .assistant_message .md-editor-previewOnly {
    background-color: rgb(214, 214, 214);
  }

  .assistant_message .message_main::after {
    content: "";
    position: absolute;
    display: block;
    width: 0;
    height: 0;
    border-right: 10px solid rgb(214, 214, 214);
    border-top: 2px solid transparent;
    border-bottom: 10px solid transparent;
    top: 10px;
    left: -10px;
  }

  .thinking {
    position: relative;
    color: rgb(74, 74, 117);
    font-size: small;
  }

  .thinking:before {
    content: "思考过程："
  }

  .message_foot {
    position: relative;
    height: fit-content;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }

  .reanswer {
    position: relative;
    width: fit-content;
    height: 20px;
  }

  .reanswer button {
    position: relative;
    outline: none;
    border: none;
    padding: 5px;
    border-radius: 5px;
    color: #2e2e2e;
    background-color: rgb(214, 214, 214);
    transition: all 0.5s;
    cursor: pointer;
  }

  .reanswer button:hover {
    background-color: rgb(255, 255, 255);
    color: rgb(25, 150, 62);
  }

  .abort_generate {
    position: relative;
    width: fit-content;
    height: 20px;
  }

  .abort_generate button {
    position: relative;
    outline: none;
    border: none;
    padding: 5px;
    border-radius: 5px;
    color: #2e2e2e;
    background-color: rgb(214, 214, 214);
    transition: all 0.5s;
    cursor: pointer;
  }

  .abort_generate button:hover {
    background-color: rgb(255, 255, 255);
    color: rgb(150, 25, 25);
  }

  .tool_message {
    justify-content: center;
    align-items: center;
  }

  .message_main.tool {
    display: flex;
    flex-direction: column;
    color: #7e7e7e;
    font-size: small;
    text-align: center;
  }

  .tool_name_item {
    margin-right: 10px;
    margin-bottom: 5px;
  }

  .tool_result_item {
    overflow-y: auto;
    white-space: wrap;
    text-overflow: ellipsis;
    max-height: 100px;
  }

  .tool_box {
    position: relative;
    display: flex;
    flex-direction: row;
  }

  .message_fade_in-enter-active,
  .message_fade_in-leave-active {
    transition: all 0.5s;
  }

  .message_fade_in-enter-from,
  .message_fade_in-leave-to {
    opacity: 0;
  }

  .upload_file {
    cursor: pointer;
  }

  .attachment {
    position: relative;
    display: flex;
    max-width: 70%;
    align-items: center;
  }

  .attachment_list {
    display: flex;
    flex-direction: row;
    align-items: center;
    height: 100%;
  }

  .attachment_name {
    position: relative;
    max-width: 65px;
    max-height: 65px;
    overflow: hidden;
    text-wrap: nowrap;
    text-overflow: ellipsis;
    color: black;
    background-color: white;
  }

  .preview_img {
    position: relative;
    max-width: 65px;
    max-height: 65px;
  }

  .clear_messages {
    position: relative;
    height: 100%;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
  }

  .message_send_box {
    position: absolute;
    bottom: 0;
    height: 200px;
    width: 100%;
    box-sizing: border-box;
    padding: 5px;
    border-top: 1px solid grey;
  }

  .message_send_header {
    position: relative;
    width: 100%;
    height: 50px;
    margin-bottom: 3px;
    font-size: small;
    display: flex;
    overflow-x: auto;
  }

  .message_send_header div {
    margin-right: 5px;
  }

  .message_send_body {
    position: relative;
    height: calc(100% - 55px);
    margin-bottom: 2px;
  }

  .input_message {
    width: 100%;
    height: 100%;
    resize: none;
    outline: none;
    border: none;
    background-color: rgb(224, 224, 224);
    border-radius: 5px;
  }

  .message_send_foot {
    position: absolute;
    right: 5px;
    bottom: 5px;
    padding: 5px 10px 5px 10px;
    border-radius: 5px;
    background-color: rgb(45, 199, 109);
    text-align: center;
    transition: all 0.5s;
  }

  .message_send_foot:hover {
    cursor: pointer;
    background-color: rgb(25, 150, 62);
    color: white;
  }

  .message_send_foot.generating:hover {
    cursor: not-allowed;
  }
}
</style>
