<script>
import CSlider from "@/components/CSlider.vue";
import axios from 'axios';
import { MdPreview, MdEditor } from 'md-editor-v3';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import 'md-editor-v3/lib/style.css'
import * as echarts from 'echarts';
import { ref } from "vue";

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
            systemInfoChart: null,
            // 各种状态
            status:{
                drawer: true,
                // 是否正在生成
                generating: false,
                // 流式传输终止信号
                abortSignal: null,
                // 如果模型是推理型的，这里存储其推理状态
                thinking: false,
                // 系统信息列表
                dateList: [],
                cpuInfoList: [],
                memInfoList: [],
            },
            // 模型列表
            modelList: ["Qwen/Qwen2.5-32B-Instruct"],
            // 消息
            message: "",
            // 消息列表
            messages: [],
            // 支持的文件类型
            supportedFileTypes: "",
            // 正在上传处理的文件列表
            uploadingFiles:[],
            fileList: [],
            currentRelatives:[],
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
        async getSupportedFileTypes(){
            // 获取支持的文件类型
            axios.get("/api/rag/supported_file_types").then(rsp=>{
                this.supportedFileTypes = rsp.data;
            });
        },
        getFileType(){
            // 通过文件判断文件类型，当前只支持文本，因此返回文本类型，这里应该加上文件参数
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
        async getSystemInfo(){
            const self = this;
            axios.get("/api/system_info").then(rsp=>{
                const data = rsp.data;
                const date = new Date();
                const cpuUsed = data["cpu"]["used"];
                const memUsed = data["memery"]["memRealUsed"];
                const memTotal = data["memery"]["memTotal"];
                self.status.dateList.push(date);
                self.status.cpuInfoList.push([date, cpuUsed]);
                self.status.memInfoList.push([date, memUsed / 1024]);
                if(self.status.dateList.length > 10){
                    self.status.dateList.shift();
                    self.status.cpuInfoList.shift();
                    self.status.memInfoList.shift();
                }
                let option = {
                    yAxis:[{
                        type: 'value',
                        max: memTotal / 1024,
                        name: "内存使用"
                    }],
                    series:[{
                        name: "CPU使用率",
                        yAxisIndex: 0,
                        data: self.status.cpuInfoList
                    },{
                        name: "内存使用",
                        yAxisIndex: 1,
                        data: self.status.memInfoList
                    }]
                };
                self.systemInfoChart.setOption(option);
                setTimeout(this.getSystemInfo, 1000);
            });
        },
        initSystemInfoCharts(){
            let aim = this.$refs["system_info"];
            this.systemInfoChart = echarts.init(aim);
            let option = {
                title: {
                    text: "系统资源监控"
                },
                legend: {                         // 图例设置
                    data: ['CPU使用率', '内存使用'],
                    bottom: 10                      // 图例位于底部
                },
                animation: false,
                xAxis: {
                    type: 'time',
                    boundaryGap: false,
                    axisLabel:{
                        formatter: "{hh}:{mm}:{ss}",
                        hideOverlap: true,
                        rotate: 45
                    }
                },
                yAxis:[{
                    type: 'value',
                    max: 100,
                    min: 0,
                    name: "CPU使用率",
                    tooltip: true,
                },{
                    type: 'value',
                    max: 8,
                    min: 0,
                    name: "内存使用"
                }],
                series:[{
                    name: "CPU使用率",
                    type: 'line',
                    smooth: true,
                    yAxisIndex: 0,
                    data: this.status.cpuInfoList
                },{
                    name: "内存使用",
                    type: 'line',
                    smooth: true,
                    yAxisIndex: 1,
                    data: this.status.memInfoList
                }],
                grid:{
                    left: "40px",
                    right: "40px"
                }
            };
            this.systemInfoChart.setOption(option);
            setTimeout(this.getSystemInfo, 1000);
        },
        async initData(){
            // 初始化数据入口，在created中调用
            this.getModels();
            this.getSupportedFileTypes();
            this.getFileList();
            this.getDefaultSettings();
        },
        async getDataAfterMounted(){
            this.initSystemInfoCharts();
        },
        async getRelative(query, top_k = 4){
            const data = {
                "query": query,
                "top_k": parseInt(top_k.toFixed(0))
            };
            return axios.post("/api/rag/relatives", data);
        },
        // 此处往下是逻辑处理
        formatChatRequestMessage(){
            // 格式化消息
            const prompt = this.message;
            this.message = "";
            const data = {
                "prompt": prompt,
                "model": this.model,
                "attachments": [],      // 暂时不支持附件
                "settings": {...this.settings},
                "message_list": [...this.messages]
            }
            data.settings.temperature /= 100;
            data.settings.top_k = parseInt(data.settings.top_k);
            // 将用户的消息添加到消息列表中
            this.messages.push({
                "role": "user",
                "content": prompt,
                "timestamp": new Date().toLocaleDateString()
            });
            // 将模型的回复先添加至消息列表，当接收到消息时往内容中流式填充Token
            this.messages.push({
                "role": "assistant",
                "content": "",
                "timestamp": new Date().toLocaleDateString(),
                "contextSearchResult": []
            });
            // 获取相关文件
            this.getRelative(prompt, this.settings.top_k).then(rsp=>{
                this.currentRelatives = [];
                rsp.data.forEach((r)=>{
                    this.currentRelatives.push({
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
        uploadRAGFile(){
            const uploadEle = this.$refs["upload_file"];
            const file = uploadEle.files[0];
            if(file === undefined) return;
            const file_name = file.name;
            const type = file.type;
            const data = new FormData();
            this.uploadingFiles.push({
                fileName: file_name,
                fileType: type,
                progress: 0
            });
            data.append("upload_file", file);
            const url = "/api/rag/upload_file";
            const self = this;
            fetchEventSource(url, {
                method: "POST",
                openWhenHidden: true,
                body: data,
                onmessage: self.handleUploadOnMessage,
                onclose: ()=>{self.handleUploadOnClose(file_name);},
                onerror: self.handleUploadOnError
            }).then(()=>{
                self.handleUploadEnd(file_name);
            })
        },
        SSEFetchCore(url, data){
            /**
             * 流式消息传输核心，只负责发起请求，处理在下方的函数中
             * @param url: 请求地址
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
            }).then(self.handleSSEEnd)
        },
        // 此处往下是事件处理
        handleUploadOnMessage(msg){
            // 上传文件回调，这里后端会流式传输文件处理进度
            if(msg.data === undefined || !msg.data) return;
            const progress = JSON.parse(msg.data);
            const idx = progress["idx"];
            const total = progress["total"];
            const file_name = progress["file_name"]
            this.uploadingFiles.forEach((f)=>{
                if(f.fileName === file_name){
                    f.progress = ((idx + 1) / total * 100).toFixed(2);
                }
            });
        },
        handleUploadOnError(e){
            console.log(e);
        },
        handleUploadOnClose(file_name){
            this.uploadingFiles = this.uploadingFiles.filter((f)=>{
                return f.fileName !== file_name;
            });
        },
        handleUploadEnd(file_name){
            this.uploadingFiles = this.uploadingFiles.filter((f)=>{
                return f.fileName !== file_name;
            });
            this.getFileList();
        },
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
            this.handleToMessageBottom();
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
            this.messages[this.messages.length - 1].contextSearchResult = [...this.currentRelatives];
        },
        handleToMessageBottom(){
            const chatContainer = this.$refs["chat_container"];
            chatContainer.scrollTo({
                top: chatContainer.scrollHeight,
                behavior: "smooth"
            });
        },
        handleInputKeyDown(e){
            // 回车发送消息处理
            if(!e.shiftKey && e.keyCode === 13){
                e.preventDefault();
                // 发送消息
                this.sendMessage();
            }
        },
        handleDeleteFile(file_name){
            axios.delete("/api/rag/delete_file/"+file_name).then((rsp)=>{
                this.getFileList();
            });
        },
        handleTestButton(){
            // 测试按钮，用作开发中的各项测试
            // this.getRelative(this.message, this.settings.top_k).then(rsp=>{
            //     console.log(rsp);
            // });
            console.log(this.fileList);
        }
    },
    created(){
        this.initData();
    },
    mounted(){
        this.getDataAfterMounted();
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
                <div class="file_item">
                    <label for="upload_file" style="cursor: pointer;">
                        <div class="file_preview">
                            <!-- 上传图标 -->
                        </div>
                        <div class="file_name">
                            上传文件    
                        </div>
                    </label>
                    <input type="file" @change="uploadRAGFile" style="display: none;" :accept="supportedFileTypes" id="upload_file" name="upload_file" ref="upload_file" />
                </div>
                <div class="file_item" v-for="(file, idx) of uploadingFiles" :key="idx">
                    <div class="file_preview ">
                        <div class="uploading_status">
                            <div class="uploading_label">处理进度</div>
                            <div class="uploading_progress" :class="{uploaded: parseInt(file.progress) >= 100, uploading: file.progress < 100}">{{ file.progress }}%</div>
                        </div>
                    </div>
                    <div class="file_name uploading">{{file.fileName}}</div>
                </div>
                <div class="file_item" v-for="(file, idx) of fileList" :key="idx">
                    <div class="delete_rag_file" @click="handleDeleteFile(file.fileName)">删除</div>
                    <div class="file_preview">
                        <img :src="'/api/download_file/' + file.fileName"
                        :alt="file.fileName"
                        v-if="file.fileType.indexOf('image') != -1">
                    </div>
                    <div class="file_name uploaded">{{file.fileName}}</div>
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
        <div class="left_bar_foot">
            <div class="system_info" ref="system_info">
                <!-- 使用ECharts折线图，在一副图中绘制CPU与内存使用率曲线 -->
            </div>
        </div>
    </div>
    </Transition>
    <div class="main">
        <div class="chat_container" ref="chat_container">
            <div class="chat_title">
                <h3>RAG测试</h3>
            </div>
            <TransitionGroup name="message">
                <div class="message" v-for="(message, idx) of messages" :key="idx" :class="message.role">
                    <div class="message_header">{{ message.timestamp }}</div>
                    <div class="message_body">
                        <MdPreview v-model="message.content" :code-foldable="false" v-if="message.content !== ''"></MdPreview>
                        <div v-else>生成中.....</div>
                        <div class="message_foot">
                            <!-- 参考搜索的上下文结果 -->
                            <div class="relative_list" v-if="message.role === 'assistant' && message.contextSearchResult.length !== 0">
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