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

## 自定义工具
在`script/tools/tools.py`中，按照指定格式书写工具注释，`prompt`模块导入工具时会自动调用相应的解析函数生成工具列表与其相应的描述并嵌入System-Prompt中，
具体的格式如下：

```python
def tool(**kwargs):
    """
    工具描述
    --------------------
    :param arg1: 参数1描述
    :param arg2: 参数2描述
    ...
    :type arg1: 参数1类型
    :type arg2: 参数2类型
    ...
    :enum arg1: 参数1可选值
    :required: arg1, arg2
    """
    # 工具主要部分
    return  # 返回值
```

其中，工具描述下的分割线<strong style="color: red">必不可少</strong>，这是因为这是用于区分工具描述与参数描述的重要部分。具体如何解析的参考`script/tools/__init__.py`中的`simple_tool_des`方法，方法很简单，是暴力解析的。

## 问题

1. 目前使用System-Prompt让模型结构化输出，但模型上下文有限，多轮对话过后可能不会结构化输出或忘记调用工具，后续需要改进。

2. 搜索工具使用`urllib3`请求[bing](https://www.bing.com)，请求可能不成功。

3. 较多的工具会导致较长的System-Prompt，可能考虑优化。

4. RAG部分研究还在进行......