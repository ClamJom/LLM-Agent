import sys
import inspect
import tools.tools as tools

from typing import List


def get_all_tool_names():
    current_module = sys.modules[tools.__name__]
    all_names = []

    # 获取当前模块中定义的顶层函数
    for name, obj in inspect.getmembers(current_module):
        if inspect.isfunction(obj) and obj.__module__ == current_module.__name__:
            all_names.append(name)

    # 获取当前模块中定义的类的方法
    for cls_name, cls in inspect.getmembers(current_module, inspect.isclass):
        if cls.__module__ != current_module.__name__:
            continue
        # 遍历类的__dict__以获取类自身定义的方法
        for name, attr in cls.__dict__.items():
            # 包含实例方法、静态方法和类方法
            if inspect.isfunction(attr) or isinstance(
                attr, (staticmethod, classmethod)
            ):
                all_names.append(f"{cls_name}.{name}")

    return all_names


def get_all_tools():
    current_module = sys.modules[tools.__name__]
    all_tools = []

    # 获取当前模块中定义的顶层函数
    for name, obj in inspect.getmembers(current_module):
        if inspect.isfunction(obj) and obj.__module__ == current_module.__name__:
            all_tools.append({"name": name, "obj": obj})

    # 获取当前模块中定义的类的方法
    for cls_name, cls in inspect.getmembers(current_module, inspect.isclass):
        if cls.__module__ != current_module.__name__:
            continue
        # 遍历类的__dict__以获取类自身定义的方法
        for name, attr in cls.__dict__.items():
            # 包含实例方法、静态方法和类方法
            if inspect.isfunction(attr) or isinstance(
                attr, (staticmethod, classmethod)
            ):
                all_tools.append({"name": f"{cls_name}.{name}", "obj": attr})
    return all_tools


def call_tool_by_name(tool_name, *args, **kwargs):
    all_tools = get_all_tools()
    for tool in all_tools:
        if tool["name"] == tool_name:
            return tool["obj"](*args, **kwargs)


def get_tool_description():
    """
    生成所有工具的描述，只对如下格式的工具有效：
    ```python
    def function_name(param1, param2):
        '''
        功能描述
        --------------------
        :param param1: 参数1的描述
        :param param2: 参数2的描述
        :type param1: 参数1的类型
        :type param2: 参数2的类型
        :required param1,param2
        '''
        # 函数主体
    ```
    """
    all_tools: List[function] = get_all_tools()
    tool_descriptions = []
    for tool in all_tools:
        # 获取函数的文档
        function_doc = tool["obj"].__doc__
        # 将文档分为功能描述和参数描述
        function_des = (
            function_doc.split("--------------------")[0] if function_doc else ""
        )
        function_des = function_des.replace("\n", "").strip()
        function_defination = (
            function_doc.split("--------------------")[1] if function_doc else ""
        )
        # 解析参数描述
        parameters = {}
        required = []
        for lines in function_defination.split("\n"):
            lines = lines.strip()
            if lines.startswith(":param"):
                # 解析参数定义
                name = lines.split(":param ")[1].split(":")[0].strip()
                des = lines.split(":param ")[1].split(":")[1].strip()
                parameters[name] = des
            elif lines.startswith(":required:"):
                # 解析必填参数
                required = [name for name in lines.split(":required: ")[1].split(",")]
            elif lines.startswith(":type"):
                # 解析参数类型
                name = lines.split(":type ")[1].split(":")[0].strip()
                param_type = lines.split(":type ")[1].split(":")[1].strip()
                if name in parameters:
                    des = parameters[name]
                    parameters[name] = {"description": des, "type": param_type}
                else:
                    parameters[name] = {"description": "", "type": param_type}
            elif lines.startswith(":enum"):
                name = lines.split(":enum")[1].split(":")[0].strip()
                enum = lines.split(":enum")[1].split(":")[1].strip()
                if type(parameters[name]) == dict:
                    parameters[name]["enum"] = enum
                else:
                    des = parameters[name]
                    parameters[name] = {"description": des, "enum": enum}
        current_tool_des = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": function_des,
                "parameters": {"type": "object", "properties": parameters},
            },
        }
        if required:
            current_tool_des["function"]["parameters"]["required"] = required
        tool_descriptions.append(current_tool_des)
    return tool_descriptions


def simple_tool_des():
    all_tools = get_all_tools()
    tool_des = ""
    for tool in all_tools:
        # 获取函数的文档
        function_doc = tool["obj"].__doc__
        # 将文档分为功能描述和参数描述
        function_des = (
            function_doc.split("--------------------")[0] if function_doc else ""
        )
        function_des = function_des.replace("\n", "").strip()
        function_defination = (
            function_doc.split("--------------------")[1] if function_doc else ""
        )
        current_des = "工具名：{}\n工具描述：{}\n".format(tool["name"], function_des)
        param_dict = {}
        required = ""
        for lines in function_defination.split("\n"):
            lines = lines.strip()
            if lines.startswith(":param"):
                # 解析参数定义
                name = lines.split(":param ")[1].split(":")[0].strip()
                des = lines.split(":param ")[1].split(":")[1].strip()
                # current_des += "参数名：{} 参数说明：{} ".format(name, des)
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "参数说明：{} ".format(des)
            if lines.startswith(":type"):
                # 解析参数类型
                name = lines.split(":type ")[1].split(":")[0].strip()
                param_type = lines.split(":type ")[1].split(":")[1].strip()
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "参数类型：{} ".format(param_type)
            if lines.startswith(":enum"):
                # 解析参数可选值
                name = lines.split(":enum")[1].split(":")[0].strip()
                enum_des = lines.split(":enum")[1].split(":")[1].strip()
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "参数可选值：{} ".format(enum_des)
            if lines.startswith(":required:"):
                # 解析必填参数
                required = lines.split(":required: ")[1]
        if param_dict != {}:
            current_des += "参数：\n"
            for name, des in param_dict.items():
                current_des += "参数名：{} {}\n".format(name, des)
        else:
            current_des += "无参数\n"
        if required:
            current_des += "必填参数：{} \n".format(required)
        current_des += "\n"
        tool_des += current_des
    return tool_des


def simple_tool_des_en():
    all_tools = get_all_tools()
    tool_des = ""
    for tool in all_tools:
        # 获取函数的文档
        function_doc = tool["obj"].__doc__
        # 将文档分为功能描述和参数描述
        function_des = (
            function_doc.split("--------------------")[0] if function_doc else ""
        )
        function_des = function_des.replace("\n", "").strip()
        function_defination = (
            function_doc.split("--------------------")[1] if function_doc else ""
        )
        current_des = "Tool name: {}\nTool description: {}\n".format(
            tool["name"], function_des
        )
        param_dict = {}
        required = ""
        for lines in function_defination.split("\n"):
            lines = lines.strip()
            if lines.startswith(":param"):
                # 解析参数定义
                name = lines.split(":param ")[1].split(":")[0].strip()
                des = lines.split(":param ")[1].split(":")[1].strip()
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "Parameter description: {} ".format(des)
            if lines.startswith(":type"):
                # 解析参数类型
                name = lines.split(":type ")[1].split(":")[0].strip()
                param_type = lines.split(":type ")[1].split(":")[1].strip()
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "Parameter type: {} ".format(param_type)
            if lines.startswith(":enum"):
                # 解析参数可选值
                name = lines.split(":enum")[1].split(":")[0].strip()
                enum_des = lines.split(":enum")[1].split(":")[1].strip()
                if name not in param_dict:
                    param_dict[name] = ""
                param_dict[name] += "Available parameter value: {} ".format(enum_des)
            if lines.startswith(":required:"):
                # 解析必填参数
                required = lines.split(":required: ")[1]
        if param_dict != {}:
            current_des += "Parameter:\n"
            for name, des in param_dict.items():
                current_des += "Parameter Name: {} {}\n".format(name, des)
        else:
            current_des += "No parameter needed for this tool\n"
        if required:
            current_des += "Required parameter list: {} \n".format(required)
        current_des += "\n"
        tool_des += current_des
    return tool_des
