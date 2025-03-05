<script>
import CSlider from "@/components/CSlider.vue";
import axios from 'axios';
import { MdPreview, MdEditor } from 'md-editor-v3';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import 'md-editor-v3/lib/style.css'

export default{
    components:{
        CSlider,
        MdPreview,
        MdEditor
    },
    data(){
        return{
            model: "Qwen/Qwen2.5-32B-Instruct",
            settings:{
                system_prompt: "你是一个智能客服，回答用户的各项问题。如果用户的问题与某些文件相关，这里会附上相关的信息，请总结其中的信息并根据你已有的知识回复用户相关问题。",
                // 温度，记得用Slider值除以100
                temperature: 70,
                // 搜索文档相关性最高的前top_k个上下文
                top_k: 4,
                // 默认流式传输
                stream: true
            },
            // 各种状态
            status:{
                drawer: true,
                // 是否正在生成
                generating: false,
                // 流式传输终止信号
                abortSignal: null,
                // 如果模型是推理型的，这里存储其推理状态
                thinking: false
            },
            // 模型列表
            modelList: ["Qwen/Qwen2.5-32B-Instruct"],
            // 消息
            message: "",
            // 消息列表
            messages: [],
            // 当前文件处理进度，储存文件向量化进度
            currentFileHandleProgress:{
                fileName: "",
                progress: 0
            },
            fileList: [{
                fileName: "test_file.txt",
                fileType: "file/text"
            }]
        }
    },
    methods:{
        // 此处往下是数据获取与初始化
        async getModels(){
            // 获取模型列表
            axios.get("/api/models").then(rsp=>{
                this.modelList = rsp.data;
            });
        },
        getFileType(){
            // 通过文件判断文件类型，当前只支持文本，因此返回文本类型
            return "file/text"
        },
        async getFileList(){
            // 获取已上传处理过的文件列表
            axios.get("/api/rag/file_list").then(rsp=>{
                this.fileList = []
                rsp.data.forEach((f)=>{
                    this.fileList.push({
                        fileName: f,
                        fileType: this.getFileType(f)
                    });
                });
            });
        },
        async getDefaultSettings(){
            // 获取默认设置
            axios.get("/api/rag/default_settings").then(rsp=>{
                const settings =  rsp.data;
                this.model = settings["model"];
                this.settings.system_prompt = settings["system_prompt"]
                this.settings.temperature = settings["temperature"] * 100;
                this.settings.top_k = settings["top_k"];
            });
        },
        async initData(){
            // 初始化数据入口，在created中调用
            this.getModels();
            this.getFileList();
            this.getDefaultSettings();
        },
        async getRelative(query, top_k = 4){
            return axios.get(`/api/rag/relatives?query=${query}&top_k=${top_k}`);
        },
        // 此处往下是逻辑处理
        formatChatRequestMessage(){
            // 格式化消息
            const prompt = this.message;
            this.message = "";
            const data = {
                "prompt": prompt,
                "model": this.model,
                "attachments": [],
                "settings": {...this.settings},
                "message_list": [...this.messages]
            }
            this.messages.push({
                "role": "user",
                "content": prompt,
                "timestamp": new Date().toLocaleDateString()
            });
            this.messages.push({
                "role": "assistant",
                "content": "",
                "timestamp": new Date().toLocaleDateString(),
                "contextSearchResult": []
            });
            this.getRelative(prompt, this.settings.top_k).then(rsp=>{
                rsp.data.forEach((r)=>{
                    this.messages[this.messages.length - 1].contextSearchResult.push({
                        "fileName": r["file_name"],
                        "url": "",
                        "contextChunk": {
                            "start": r["start"],
                            "end": r["end"],
                            "context": r["context"],
                            "relative": r["relative"]
                        }
                    });
                });
            });
            return data;
        },
        sendMessage(){
            this.status.generating = true;
            this.status.abortSignal = new AbortController();
            const data = this.formatChatRequestMessage();
            this.SSEFetchCore("/api/rag/chat", data);
        },
        SSEFetchCore(url, data){
            /**
             * @param data: 数据。数据处理不会在此处，必须在传输前处理成需要的格式
             */
            const self = this;
            fetchEventSource(url, {
                method: "POST",
                headers: {
                    "Content-Type" : "application/json"
                },
                signal: self.status.abortSignal.signal,
                body: JSON.stringify(data),
                onmessage: self.handleSSEFetchOnMessage,
                onclose: self.handleSSEFetchOnClose,
                onerror: self.handleSSEFetchOnError
            }).then(()=>self.handleSSEEnd)
        },
        // 此处往下是事件处理
        handleSSEFetchOnMessage(msg){
            // 流式传输消息处理
            // 终止条件
            if(msg.data === "[DONE]") return;
            let data = JSON.parse(msg.data);
            if(data["choices"][0]["finish_reason"] === "stop" || data["choices"][0]["delta"]["content"] === undefined) 
                return;
            // 对生成的每一个token进行处理
            if(data["choices"][0]["delta"]["content"] === null){
                let token = data["choices"][0]["delta"]["reasoning_content"];
                if(this.messages[this.messages.length - 1].content === ""){
                    this.messages[this.messages.length - 1].content += "<div class='thinking'>";
                }
                this.messages[this.messages.length - 1].content += token;
                this.status.thinking = true;
            }else{
                let token = data["choices"][0]["delta"]["content"];
                if(this.status.thinking){
                    // 推理型的模型开始正常输出时代表其推理过程已经结束，
                    this.messages[this.messages.length - 1].content += "</div>\n";
                    this.status.thinking = false
                }
                this.messages[this.messages.length - 1].content += token;
            }
        },
        handleSSEFetchOnError(e){
            // 流式传输错误处理
            console.log(e);
            this.generating = false;
            if(this.status.abortSignal !== null){
                this.status.abortSignal.abort();
                this.status.abortSignal = null;
            }
        },
        handleSSEFetchOnClose(){
            // 流式传输关闭处理
            this.generating = false;
            if(this.status.abortSignal !== null){
                this.status.abortSignal.abort();
                this.status.abortSignal = null;
            }
        },
        handleSSEEnd(){
            // 流式传输结束后的处理
            this.generating = false;
            if(this.status.abortSignal !== null){
                this.status.abortSignal.abort();
                this.status.abortSignal = null;
            }
        },
        handleInputKeyDown(e){
            // 回车发送消息处理
            if(!e.shiftKey && e.keyCode === 13){
                e.preventDefault();
                // 发送消息
                this.sendMessage();
            }
        },
        handleTestButton(){
            // 测试按钮，用作开发中的各项测试
            this.getRelative(this.message, this.settings.top_k).then(rsp=>{
                console.log(rsp);
            });
        }
    },
    created(){
        this.initData();
    }
}
</script>

<template>
<div class="body">
    <Transition name="drawer">
    <div class="left_bar" v-if="status.drawer">
        <div class="left_bar_header">
            <div class="file_list_header">文件</div>
            <div class="file_list">
                <div class="file_item" v-for="(file, idx) of fileList" :key="idx">
                    <div class="file_preview">
                        <img :src="'/api/download_file/' + file.fileName"
                         :alt="file.fileName"
                         v-if="file.fileType.indexOf('image') != -1">
                    </div>
                    <div class="file_name">{{file.fileName}}</div>
                </div>
                <div class="file_item">
                    <div class="file_preview">
                        <!-- 上传图标 -->
                    </div>
                    <div class="file_name">上传文件</div>
                </div>
            </div>
        </div>
        <div class="left_bar_body">
            <div class="settings">
                <div class="setting_item">
                    <div class="setting_title">模型</div>
                    <div class="setting_body">
                        <select v-model="model" name="model" id="model">
                            <option v-for="(model, idx) of modelList" :key="idx" :value="model">{{ model }}</option>
                        </select>
                    </div>
                </div>
                <div class="setting_item">
                    <div class="setting_title">系统提示词</div>
                    <div class="setting_body">
                        <textarea 
                        :value="settings.system_prompt" 
                        name="system_prompt" 
                        id="system_prompt"
                        rows="5"
                        style="resize: none; width: calc(100% - 5px);">
                        </textarea>
                    </div>
                </div>
                <div class="setting_item">
                    <div class="setting_title">温度</div>
                    <div class="setting_body">
                        <CSlider v-model="settings.temperature"
                        :min="10" 
                        :max="100"
                        :caster="(value)=>{return (value / 100).toFixed(2);}">
                        </CSlider>
                    </div>
                </div>
                <div class="setting_item">
                    <div class="setting_title">最匹配的N个结果</div>
                    <div class="setting_body">
                        <CSlider v-model="settings.top_k"
                        :min="1" 
                        :max="10">
                        </CSlider>
                    </div>
                </div>
                <div class="setting_item">
                    <div class="setting_title">测试</div>
                    <div class="setting_body">
                        <button @click="handleTestButton">测试</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    </Transition>
    <div class="main">
        <div class="chat_container">
            <div class="chat_title">
                <h3>RAG测试</h3>
            </div>
            <TransitionGroup name="message">
                <div class="message" v-for="(message, idx) of messages" :key="idx" :class="message.role">
                    <div class="message_header">{{ message.timestamp }}</div>
                    <div class="message_body">
                        <MdPreview v-model="message.content"></MdPreview>
                        <div class="message_foot">
                            <!-- 参考搜索的上下文结果 -->
                            <div class="relative_list" v-if="message.role === 'assistant' && message.contextSearchResult">
                                <div class="relative_title">参考文件</div>
                                <div class="relative_item" v-for="(relative, idx) of message.contextSearchResult" :key="idx">
                                    <div class="related_file_name">{{ relative.fileName }}</div>
                                    <div class="lines">
                                        行：
                                        <span>{{ relative.contextChunk.start }}</span>
                                        -
                                        <span>{{ relative.contextChunk.end }}</span>
                                    </div>
                                    <div class="correlation_rate">相关率：{{ relative.contextChunk.relative }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </TransitionGroup>
        </div>
        <div class="message_send_box">
            <div class="message_send_header">
            </div>
            <div class="message_send_body">
                <textarea 
                    name="send_message" 
                    id="send_message" 
                    placeholder="请输入消息....."
                    class="message_inputer"
                    v-model="message"
                    @keydown="handleInputKeyDown">
                </textarea>
            </div>
        </div>
    </div>
</div>
</template>

<style scoped>
@import url("../assets/rag.css");

.drawer-enter-active,
.drawer-leave-active {
    transition: all 0.5s ease-in-out;
}

.drawer-enter-from,
.drawer-leave-to{
    transform: translateX(-100%);
    opacity: 0;
}

.message-enter-active,
.message-leave-active {
    transition: all 0.3s;
}

.message-enter-from,
.message-leave-to {
    opacity: 0;
}
</style>