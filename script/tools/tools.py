import random
from datetime import datetime

"""
在这里定义工具与工具描述，如果描述的格式正确，工具会被自动解析为系统提示的一部分以便模型调用
"""


def get_current_time():
    """
    获取服务器时间，格式为"YYYY-MM-DD HH:MM:SS a"
    --------------------
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %a")


def get_random_number():
    """
    生成1到100的随机数
    --------------------
    """
    return random.randint(1, 100)


def compare(a: int | float, b: int | float):
    """
    比较两个数字的大小
    --------------------
    :param a: 第一个数字
    :param b: 第二个数字
    :type a: int | float
    :type b: int | float
    :required: a,b
    """
    if a > b:
        return "{} 大过 {}".format(a, b)
    elif a < b:
        return "{} 小于 {}".format(a, b)
    else:
        return "{} 等于 {}".format(a, b)


def internet_search(data: str):
    """
    利用搜索引擎进行搜索，返回前10条结果
    --------------------
    :param data: 需要搜索的关键词
    :type data: str
    :required: data
    """
    import urllib3
    from bs4 import BeautifulSoup

    urllib3.disable_warnings()
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    url = "https://www.bing.com/search?q={}".format(data)
    rsp = urllib3.request("GET", url, headers=header, timeout=5)
    soup = BeautifulSoup(rsp.data, "lxml")
    results = soup.find_all("li", class_="b_algo")
    summary = "搜索结果如下（不一定完整）: \n"
    index = 0
    for result in results:
        index += 1
        title = result.find("h2").text
        link = result.find("a", class_="tilk")["href"]
        des_list = result.find_all("p")
        des = ""
        for i in range(len(des_list)):
            des += "描述{}: {}\n".format(i + 1, des_list[i].text)
        # des = get_url_content(link)
        summary += "第{}条结果: \n标题: {}\n链接: {}\n描述: {}\n".format(
            index, title, link, des
        )
    if index == 0:
        summary = "没有搜索到结果"
    return summary


def get_url_content(url: str):
    """
    获取URL的内容
    --------------------
    :param url: URL地址
    :type url: str
    :required: url
    """
    import urllib3
    from bs4 import BeautifulSoup

    urllib3.disable_warnings()
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    rsp = urllib3.request("GET", url, headers=header, timeout=5)
    soup = BeautifulSoup(rsp.data, "lxml")
    return soup.find("body").text


def ask_for_leave(**kwargs):
    """
    申请请假

    时间应当按照如下格式填写:
    2025-01-01 08:00:00
    --------------------
    :param type: 请假类型
    :param reason: 请假原因
    :param start_time: 请假开始时间
    :param end_time: 请假结束时间
    :type type: str
    :type reason: str
    :type start_time: str
    :type end_time: str
    :enum type: ['事假','病假','年假','产假','陪产假','调休','其他']
    :required: type,reason,start_time,end_time
    """
    type = kwargs.get("type")
    reason = kwargs.get("reason")
    start_time = kwargs.get("start_time")
    end_time = kwargs.get("end_time")
    from datetime import datetime

    form = {
        "type": type,
        "reason": reason,
        "start_time": start_time,
        "end_time": end_time,
    }
    if not type:
        return "Type can't be empty!"
    if not reason:
        return "Reason can't be empty!"
    if not start_time:
        return "State time cant't be empty!"
    if not end_time:
        return "End time can't be empty!"
    now = datetime.now()
    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    if start_time < now:
        return "Start time can't be earlier than now!"
    end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    if end_time < start_time:
        return "End time can't be earlier than start time!"
    print("用户提交了一个请假单：{}".format(form))
    return "Leave form submitted successfully"


DEVICE_STATUS = [
    {"id": "LT1", "name": "一号灯", "status": False},
    {"id": "LT2_FL", "name": "鱼塘照明", "status": False},
    {"id": "LT3", "name": "大门照明", "status": False},
    {"id": "LT4", "name": "恒温灯", "status": True},
    {"id": "LT5", "name": "自动灯", "status": False},
    {"id": "AC1", "name": "空调", "status": False, "tempture": "N/A"},
    {"id": "CW1", "name": "洗衣机", "status": True, "time": 15, "dry": False},
]


def query_device_status():
    """
    查询设备状态，返回设备列表与其当前的状态
    --------------------
    """
    global DEVICE_STATUS
    return DEVICE_STATUS


def controll_device_statu(**kwargs):
    """
    控制设备参数与状态
    --------------------
    :param id: 设备ID
    :param status: 设备开关状态
    :param tempture: 空调的温度（如果当前设备是空调类型，可填写该参数，默认为28）
    :param dry: 洗衣机是否甩干（如果当前设备是洗衣机类型，可填写该参数，默认为False）
    :param time: 洗衣机剩余时间（如果当前设备是洗衣机类型，可填写该参数，默认为15，范围为 10-60）
    :type id: str
    :type status: bool
    :type tempture: int
    :type time: int
    :type dry: bool
    :required: id,status
    """
    global DEVICE_STATUS
    id = kwargs.get("id")
    status = kwargs.get("status")
    tempture = kwargs.get("tempture", None)
    dry = kwargs.get("dry", False)
    time = kwargs.get("time", 15)
    if id == "LT5":
        return '{"statu": "error", "msg": "无法控制自动灯: 拒绝访问"}'
    for device in DEVICE_STATUS:
        if device["id"] == id:
            device["status"] = status
            if tempture:
                if str(id).find("AC") == -1:
                    return '{"statu": "warning", "msg": "当前设备类型不可控制温度"}'
                if status:
                    device["tempture"] = tempture
                else:
                    return '{"statu": "warning", "msg": "空调设备未启动"}'
            if str(id).find("CW") != -1:
                if time < 10 or time > 60:
                    return '{"statu": "warning", "msg": "洗衣机运行时间不合法，请重试"}'
                device["dry"] = bool(dry)
                device["time"] = time
            break
    else:
        return '{"statu": "warning", "msg": "没有找到对应ID的设备"}'
    return '{"statu": "success", "msg": "设备状态已更新"}'
