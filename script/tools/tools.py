import random
from datetime import datetime

"""
在这里定义工具与工具描述，如果描述的格式正确，工具会被自动解析为系统提示的一部分以便模型调用
"""

def get_current_time():
    """
    Acquire current time of the server. The format is "YYYY-MM-DD HH:MM:SS a"
    --------------------
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %a")


def get_random_number():
    """
    Acquire a random number between 1 and 100
    --------------------
    """
    return random.randint(1, 100)

def compare(a: int | float, b: int | float):
    """
    Compare two numbers
    --------------------
    :param a: The first number
    :param b: The second number
    :type a: int | float
    :type b: int | float
    :required: a,b
    """
    if a > b:
        return "{} is big than{}".format(a, b)
    elif a < b:
        return "{} is small than {}".format(a, b)
    else:
        return "{} is euqal than {}".format(a, b)


def internet_search(data: str):
    """
    Using search engine to search data from internet
    --------------------
    :param data: The data to be searched
    :type data: str
    :required: data
    """
    import urllib3
    from bs4 import BeautifulSoup
    urllib3.disable_warnings()
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    url = "https://cn.bing.com/search?q={}".format(data)
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
        summary += "第{}条结果: \n标题: {}\n链接: {}\n描述: {}\n".format(index, title, link, des)
    if index == 0:
        summary = "没有搜索到结果"
    return summary

def ask_for_leave(**kwargs):
    """
    Apply for leave form

    Time should be formatted as follows:
    2025-01-01 08:00:00
    --------------------
    :param type: Leave type
    :param reason: Leave reason
    :param start_time: Start time of leave
    :param end_time: End time of leave
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
        "end_time": end_time
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