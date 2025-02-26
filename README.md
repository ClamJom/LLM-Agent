# LLM-Agent
一个简单的LLM代理人项目，使用硅基流动API。
使用System-Prompt让模型结构化输出与调用工具，使用不同模型处理不同模态的数据，并交给当前对话模型进行总结。

后端使用FastAPI框架，使用uvicorn作为服务器。前端使用Vue.js框架。

## 使用
1. 安装依赖

后端：Python版本：3.12.4，推荐使用虚拟环境
```console
pip install -r requirements.txt
```
前端：
```console
cd web
npm install
```

2. 配置

修改`script/setting/settings.py`中的`API_URL`与`API_KEY`为自己平台的地址与密钥，前提是平台中得有`settings`中配置的几个模型。不过也可以自己专门写:)

3. 运行

后端：直接运行`script/__main__.py`即可

前端：
```console
cd web
npm run dev
```
端口默认为5173，也可自己修改