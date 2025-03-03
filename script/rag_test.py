from llama_cpp import Llama
from transformers import AutoTokenizer
from sklearn.cluster import KMeans
from sklearn.preprocessing import Normalizer
from json import JSONEncoder
from setting import settings
from setting import prompt
from common.models import OpenAi
import numpy as np
import tqdm
import sqlite3
import json
import os
import re

tokenizer = AutoTokenizer.from_pretrained("./model/DeepSeek-R1-Distill-Qwen-1.5B")
model_path = "./model/granite-embedding-278m-multilingual-GGUF/granite-embedding-278m-multilingual-Q4_K_M.gguf"
sqlite_path = "./data/rag_search_tree.db"
embeddings = []
# 一个类中的数量
kmeans_cluster_size = 5


class SearchNode:
    # 搜索树节点
    def __init__(self, data: np.ndarray):
        self.center = data.tolist()
        self.childList: list[SearchNode] | None = None
        # self.parent = None
        # 节点描述
        self.__des = None

    def get_dis(self, x):
        # 余弦距离计算
        _x = np.dot(np.array(self.center), np.array(x))
        _y = np.dot(np.linalg.norm(np.array(self.center)), np.linalg.norm(np.array(x)))
        return _x / _y

    def set_des(self, des):
        self.__des = des

    def get_des(self):
        return self.__des


class SearchNodeEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


# 数据库操作
def create_rag_vector_database():
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()

    # Create a table to store conversations
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS rag_vector (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vector TEXT,
                    des TEXT,
                    parent_id INTEGER
                )"""
    )
    conn.commit()
    conn.close()


def insert_rag_vector(vector, des, parent_id):
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO rag_vector (vector, des)
                    VALUES (?, ?)""",
        (json.dumps(vector), des, parent_id),
    )
    conn.commit()
    conn.close()


def get_current_node_id(node: SearchNode):
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()
    res = cursor.execute(
        """SELECT id FROM rag_vector WHERE vector = ?""", (json.dumps(node.center))
    )
    current_data = res.fetchone()
    conn.close()
    return current_data[0] if current_data else None


def get_child_node(parent_id):
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()
    res = cursor.execute(
        """SELECT id FROM rag_vector WHERE parent_id = ?""", (parent_id,)
    )
    child_nodes = res.fetchall()
    conn.close()
    return child_nodes if child_nodes else []


def save_search_tree(root: SearchNode, parent_id: int = -1):
    if root is None:
        return
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO rag_vector (parent_id, vector, des) VALUES (?, ?, ?)""",
        (
            parent_id,
            json.dumps(root.center),
            root.get_des(),
        ),
    )
    conn.commit()
    new_parent_id = cursor.lastrowid
    if root.childList is None:
        return
    for child in root.childList:
        save_search_tree(child, new_parent_id)


def load_search_trees(parent_id=-1):
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    cursor = conn.cursor()
    result = cursor.execute(
        "SELECT * FROM rag_vector WHERE parent_id = ?", (parent_id,)
    )
    node_list = []
    for row in result:
        vector = json.loads(row[1])
        des = row[2]
        child = SearchNode(np.array(vector))
        child.set_des(des)
        child.childList = load_search_trees(row[0])
        if child.childList is None:
            child.childList = []
        node_list.append(child)
    return node_list


def search_tree(root: SearchNode, query_vector: np.ndarray):
    if not root.childList:
        return root.get_des()
    minDis = float("inf")
    nearestChild = None
    for i in range(len(root.childList)):
        if root.childList[i].get_dis(query_vector) < minDis:
            minDis = root.childList[i].get_dis(query_vector)
            nearestChild = root.childList[i]
    return search_tree(nearestChild, query_vector)


def split_sentences(text):
    # 通过标点分割句子
    sentences = re.split(r"(?<=[。！？. ? !])", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text, max_tokens=512):
    # 将文本按照每块最大512 Tokens分割，并保持其中的句子完整性
    sentences = split_sentences(text)
    chunks = []
    current_chunk = []
    current_token_count = 0

    for sentence in sentences:
        sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False)
        sentence_token_count = len(sentence_tokens)

        if current_token_count + sentence_token_count > max_tokens:
            # 当前块已满，保存并重置
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_token_count = sentence_token_count
        else:
            # 继续填充当前块
            current_chunk.append(sentence)
            current_token_count += sentence_token_count

    # 添加最后一个块
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def init_search_tree(node_list: list[SearchNode]):
    """
    生成一颗搜索树

    存在严重的问题，搜索结果不正确，需要优化
    ------------------
    最多有`log(总Token数 / 512) / log(每一类含有的块数)`层
    """
    # 按照设置的每一类中的数量计算总共需要分出多少个类
    n_clusters = np.ceil(len(node_list) / kmeans_cluster_size)
    n_clusters = int(n_clusters)
    # 获取所有节点的中心点（初始时中心点为其本身，因为只有一个节点）
    center_list = [data.center for data in node_list]
    # 使用K-means算法对中心点进行聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(center_list)
    if n_clusters == 1:
        # 如果只有一个类，那么已经聚类完成，搜索树已经构建到顶端，返回根节点
        root = SearchNode(kmeans.cluster_centers_[0])
        root.childList = node_list
        return root
    # 如果不止一个类，则搜索树构建还未完成，继续向上构建
    new_node_list = []
    labels = kmeans.labels_
    for i in range(n_clusters):
        # 初始化当前类的父节点
        new_node = SearchNode(kmeans.cluster_centers_[i])
        # 将属于当前类的直接点传递给父节点
        current_childs = []
        for j in range(len(labels)):
            # node_list[j].parent = new_node
            if labels[j] == i:
                current_childs.append(node_list[j])
        new_node.childList = current_childs
        # 将当前类的父节点加入新的节点列表总
        new_node_list.append(new_node)
    # 递归处理
    return init_search_tree(new_node_list)


def summary_chunk(node_list: list[SearchNode], summary_model: OpenAi.OpenAi):
    _prompt = "总结下列片段，并给出一个综合的描述（不超过300字）：\n"
    for idx, node in enumerate(node_list):
        _prompt += "片段{}:\n{}\n\n".format(idx, node.get_des())
    summary_model.messages = []
    return summary_model(_prompt)


def init_tree_with_des(
    node_list: list[SearchNode], embedding_model: Llama, summary_model: OpenAi.OpenAi
):
    """
    生成一颗搜索树，并给所有节点带上描述
    ------------------
    最多有`log(总Token数 / 512) / log(每一类含有的块数)`层
    """
    # 按照设置的每一类中的数量计算总共需要分出多少个类
    n_clusters = np.ceil(len(node_list) / kmeans_cluster_size)
    n_clusters = int(n_clusters)
    # 获取所有节点的中心点（初始时中心点为其本身，因为只有一个节点）
    center_list = [data.center for data in node_list]
    # 使用K-means算法对中心点进行聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(center_list)
    if n_clusters == 1:
        # 如果只有一个类，那么已经聚类完成，搜索树已经构建到顶端，返回根节点
        node_des = summary_chunk(node_list, summary_model)
        node_embedding = embedding_model.create_embedding(node_des)["data"][0][
            "embedding"
        ]
        node_embedding = np.array(node_embedding)
        root = SearchNode(node_embedding)
        root.childList = node_list
        root.set_des(node_des)
        return root
    # 如果不止一个类，则搜索树构建还未完成，继续向上构建
    new_node_list = []
    labels = kmeans.labels_
    for i in range(n_clusters):
        # 将属于当前类的子节点传递给父节点
        current_childs = []
        for j in range(len(labels)):
            # node_list[j].parent = new_node
            if labels[j] == i:
                current_childs.append(node_list[j])
        node_des = summary_chunk(current_childs, summary_model)
        print(node_des)
        node_embedding = embedding_model.create_embedding(node_des)["data"][0][
            "embedding"
        ]
        node_embedding = np.array(node_embedding)
        # 初始化当前类的父节点
        new_node = SearchNode(node_embedding)
        # 将当前类的父节点加入新的节点列表中
        new_node.childList = current_childs
        new_node_list.append(new_node)
        new_node.set_des(node_des)
    # 递归处理
    return init_search_tree(new_node_list)


def main():
    # 加载本地模型，生成文本向量并构建搜索树
    model = Llama(model_path=model_path, embedding=True, n_ctx=512, verbose=False)
    print("已加载模型，开始计算embedding...")
    # 分块计算embedding
    embeddings = []
    with open("./data/tb1.txt", "rt", encoding="utf-8") as f:
        content = f.read()
        chunks = chunk_text(content)
        for chunk in tqdm.tqdm(chunks):
            embedding = model.create_embedding(chunk)
            embeddings.append(embedding["data"][0]["embedding"])
    # with open("embeddings.json", "rt") as f:
    #     embeddings = json.loads(f.read())
    print("Embedding计算完成，开始生成聚类....")
    # 聚类，每一类最终变成搜索树的叶。叶的中点再次聚类，形成叶的父节点，依此类推。
    embeddings = np.array(embeddings)
    with open('./data/embeddings.json', 'wt') as f:
        result = json.dumps(embeddings.tolist())
        f.write(result)
    
    # 这一段的Normalizer操作是为了使K-Means聚类方法的距离函数与余弦距离函数一致
    normalizer = Normalizer("l2")
    embeddings = normalizer.transform(embeddings)
    leaf_node_list = []
    for idx, embedding in tqdm.tqdm(enumerate(embeddings), total=len(embeddings)):
        node = SearchNode(embedding)
        des = chunks[idx].replace("\u3000", "")
        node.set_des(des)
        leaf_node_list.append(node)

    summary_model = OpenAi.OpenAi(
        url=settings.API_URL,
        api_key=settings.API_KEY,
        model=settings.TEXT_HANDLER,
        prompt=prompt.TEXT_PROMPT,
        temperature=0.1,
    )
    root = init_tree_with_des(leaf_node_list, model, summary_model)
    print("聚类及搜索树生成完成....")
    root.set_des("三体·一")
    with open("search_tree.json", "w") as f:
        result = json.dumps(root, indent=4, cls=SearchNodeEncoder)
        f.write(result)
    print("保存搜索树至Sqlite....")
    create_rag_vector_database()
    save_search_tree(root)
    print("保存完成.")
    model._sampler.close() if model._sampler else None
    model.close()


def test():
    # 测试搜索树
    root = load_search_trees()[0]
    model = Llama(model_path=model_path, verbose=False, n_ctx=512, embedding=True)
    query = "三体世界是怎么样的？"
    embedding = model.create_embedding(query)["data"][0]["embedding"]
    result = search_tree(root, embedding)
    print(result)
    model._sampler.close() if model._sampler else None
    model.close()


def search_list_test():
    # 直接搜索列表，不搜索树。需要先生成`embedding.json`，或仿照`main`及时生成
    with open("./data/tb1.txt", "rt", encoding="utf-8") as f:
        content = f.read()
        chunks = chunk_text(content)
        f.close()
    with open("./data/embeddings.json", "rt") as f:
        embeddings = json.loads(f.read())
        f.close()
    model = Llama(model_path=model_path, verbose=False, n_ctx=512, embedding=True)
    query = "三体世界是怎么样的？"
    embedding = model.create_embedding(query)["data"][0]["embedding"]
    distant = []
    for embe in embeddings:
        _x = np.dot(np.array(embe), np.array(embedding))
        _y = np.dot(np.linalg.norm(embe), np.linalg.norm(embedding))
        distant.append(_x / _y)
    sort_list = np.argsort(distant)
    top5 = sort_list[-5:]
    for idx in top5:
        print(chunks[idx])
    model._sampler.close() if model._sampler else None
    model.close()


if __name__ == "__main__":
    if os.path.exists(sqlite_path):
        os.remove(sqlite_path)
    main()
    test()