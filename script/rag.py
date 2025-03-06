import numpy as np
import sqlite3
import chromadb
import json
import uuid
import os

from transformers import AutoTokenizer
from llama_cpp import Llama
from sklearn.cluster import KMeans
from skfuzzy.cluster import cmeans
from json import JSONEncoder

from setting import settings, prompt
from common.models import OpenAi

class SearchNode:
    def __init__(self, data: list[float]):
        # 不直接用np.ndarray是因为其无法序列化
        self.data = data
        self.child_list: list[SearchNode] | None = None
        self.des = None
        self.start_line = -1
        self.end_line = -1
    
    def get_dis(self, x: np.ndarray):
        # 使用余弦距离（即相关性）
        _x = np.dot(self.data, x)
        _y = np.dot(np.linalg.norm(np.array(self.data)), np.linalg.norm(x))
        return _x / _y

class SearchNodeEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__
    
class RAGTreeDB:
    # RAG搜索树数据库对象，封装对树形RAG搜索的操作
    # 树形结构下，对于大文件的搜索的次数与速度相较链表更优，因此这里可以采用传统数据库
    def __init__(self, file_name):
        self.path = settings.RAG_SQLITE_DATABASE_PATH
        self.create_rag_vector_database()
        self.name = file_name
    
    def create_rag_vector_database(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS rag_vector(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                start_line INTEGER,
                end_line INTEGER,
                vector TEXT,
                des TEXT,
                parent_id INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
    
    def get_node_id(self, node: SearchNode):
        # 获取节点的ID
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        res = cursor.execute(
            """SELECT id FROM rag_vector WHERE vector = ?""", (json.dumps(node.data))
        )
        current_data = res.fetchone()
        conn.close()
        return current_data[0] if current_data else None
    
    def save_search_tree(self, root: SearchNode, parent_id: int = -1):
        if root is None:
            return
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO rag_vector(file_name, start_line, end_line, vector, des, parent_id) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                self.name,
                root.start_line,
                root.end_line,
                json.dumps(root.data),
                root.des,
                parent_id,
            )
        )
        conn.commit()
        new_parent_id = cursor.lastrowid
        conn.close()
        if root.child_list is None:
            return
        for child in root.child_list:
            self.save_search_tree(child, new_parent_id)

    def __load_tree_with_parent_id(self, parent_id: int):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        result = cursor.execute("SELECT * FROM rag_vector WHERE parent_id = ?", (parent_id,))
        node_list = []
        for row in result:
            node = SearchNode(json.loads(row[4]))
            node.des = row[5]
            node.start_line = row[2]
            node.end_line = row[3]
            node.child_list = self.__load_tree_with_parent_id(row[0])
            if node.child_list is None:
                node.child_list = []
            node_list.append(node)
        conn.close()
        return node_list
    
    def get_root_nodes(self):
        # 获取所有搜索树的根节点
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM rag_vector WHERE parent_id is -1"""
        )
        result = cursor.fetchall()
        conn.close()
        node_list = []
        for row in result:
            node = SearchNode(json.loads(row[4]))
            node.des = row[5]
            node.start_line = row[2]
            node.end_line = row[3]
            node_list.append(node)
        return node_list

    def load_search_tree(self, id: int):
        # 通过ID加载搜索树
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM rag_vector WHERE id=?""", (id,)
        )
        node = cursor.fetchone()
        if node is None:
            return None
        root = SearchNode(json.loads(node[4]))
        root.des = node[5]
        root.child_list = self.__load_tree_with_parent_id(id)
        return root
    
    def load_search_tree_with_name(self, file_name: str):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM rag_vector WHERE file_name = ? and parent_id = -1""", (file_name,)
        )
        node = cursor.fetchone()
        if node is None:
            return None
        root = SearchNode(json.loads(node[4]))
        root.des = node[5]
        root.child_list = self.__load_tree_with_parent_id(node[0])
        return root
    
    def search_tree(self, root: SearchNode, query_vector: np.ndarray):
        # 搜索树
        if not root.child_list:
            return root
        minDis = float("inf")
        nearestChild = None
        for i in range(len(root.child_list)):
            if root.child_list[i].get_dis(query_vector) < minDis:
                minDis = root.child_list[i].get_dis(query_vector)
                nearestChild = root.child_list[i]
        return self.search_tree(nearestChild, query_vector)

class RAGTree:
    # 待完善.....
    def __init__(self, file_name: str):
        self.file_path = os.path.join(settings.RAG_UPLOAD_PATH, file_name)
        self.file_name = file_name
        self.rag_db = RAGTreeDB(file_name)
        self.cluster_size = settings.RAG_CLUSTER_SIZE
        self.summary = settings.RAG_INIT_TREE_WITH_DES
        self.classification_alg = settings.RAG_CLSSIFICATION_ALG

        self.tokenizer = AutoTokenizer.from_pretrained(settings.RAG_TOKENIZER_PATH_OR_NAME)
        self.max_token = settings.RAG_N_CTX
        self.n_gpu_layer = settings.RAG_EMBEDDING_GPU_LAYER
        self.embedding_model = Llama(settings.RAG_EMBEDDING_MODEL,
                                     n_ctx=self.max_token,
                                     embedding=True,
                                     verbose=False,
                                     n_gpu_layers=self.n_gpu_layer)
        self.root = None
    
    def get_file_type(self):
        # 目前只支持文本文件
        return "text"
    
    def load_file(self):
        file_type = self.get_file_type()
        if file_type == "text":
            with open(self.file_path, "rt", encoding="utf-8") as f:
                return f.read()
        else:
            return None
    
    def chunk_text(self, text: str):
        # 将文本分割为多个区块
        lines = text.split('\n')
        chunks = []
        current_chunk_token_num = 0
        current_chunk = {
            'start_line': 0,
            'end_line' : 0,
            'des': ""
        }
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            line_tokens = self.tokenizer.encode(line, add_special_tokens=False)
            if current_chunk_token_num + len(line_tokens) > self.max_token:
                current_chunk['end_line'] = idx
                current_chunk_tokens = self.tokenizer.encode(current_chunk["des"], add_special_tokens=False)
                current_chunk_tokens = current_chunk_tokens[-settings.RAG_OVERLAPPING_TOKEN:]
                overlapping_parts = self.tokenizer.decode(current_chunk_tokens)
                current_chunk_token_num = settings.RAG_OVERLAPPING_TOKEN + len(line_tokens)
                chunks.append(current_chunk)
                current_chunk = {
                    'start_line': idx,
                    'end_line' : idx,
                    'des': overlapping_parts + line
                }
            else:
                current_chunk["des"] += line + "\n"
                current_chunk_token_num += len(line_tokens)
            idx += 1
        return chunks
    
    def init_search_tree_kmeans(self, node_list: list[SearchNode]):
        n_clusters = np.ceil(len(node_list) / self.cluster_size)
        n_clusters = int(n_clusters)
        data_list = np.array([node.data for node in node_list])
        kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(data_list)
        if n_clusters == 1:
            root = SearchNode(list(kmeans.cluster_centers_[0]))
            root.child_list = node_list
            if self.summary:
                summary_model = OpenAi.OpenAi(url=settings.API_URL,
                                            api_key=settings.API_KEY,
                                            model=settings.TEXT_HANDLER,
                                            prompt=prompt.TEXT_PROMPT,
                                            temperature=0.1,)
                node_des = self.summary_chunk(node_list, summary_model)
                embedding = self.embedding_model.create_embedding(node_des)["data"][0]["embedding"]
                root.data = list(embedding)
                root.des = node_des
            return root
        new_node_list: list[SearchNode] = []
        labels = kmeans.labels_
        for i in range(n_clusters):
            child_list = []
            for j in range(len(labels)):
                if labels[j] == i:
                    child_list.append(node_list[j])
            if len(child_list) == 0:
                # 剪枝，保证每一个节点都是带有描述的
                continue
            node_data = list(kmeans.cluster_centers_[i])
            node_des = ""
            if self.summary:
                summary_model = OpenAi.OpenAi(url=settings.API_URL,
                                            api_key=settings.API_KEY,
                                            model=settings.TEXT_HANDLER,
                                            prompt=prompt.TEXT_PROMPT,
                                            temperature=0.1,)
                node_des = self.summary_chunk(child_list, summary_model)
                embedding = self.embedding_model.create_embedding(node_des)["data"][0]["embedding"]
                node_data = list(embedding)
            new_node = SearchNode(node_data)
            new_node.des = node_des
            new_node_list.append(new_node)
            new_node.child_list = child_list
        return self.init_search_tree_kmeans(new_node_list)
    
    def init_search_tree_cmeans(self, node_list: list[SearchNode]):
        n_clusters = np.ceil(len(node_list), self.cluster_size)
        n_clusters = int(n_clusters)
        data_list = np.array([node.data for node in node_list])
        cnts, u, u0, d, jm, p, fpc = cmeans(data=data_list.T, c=n_clusters, m=2, error=0.005, maxiter=100)
        if n_clusters == 1:
            root = SearchNode(list(cnts[0]))
            root.child_list = node_list
            if self.summary:
                summary_model = OpenAi.OpenAi(url=settings.API_URL,
                                            api_key=settings.API_KEY,
                                            model=settings.TEXT_HANDLER,
                                            prompt=prompt.TEXT_PROMPT,
                                            temperature=0.1,)
                node_des = self.summary_chunk(node_list, summary_model)
                embedding = self.embedding_model.create_embedding(node_des)["data"][0]["embedding"]
                root.data = list(embedding)
                root.des = node_des
            return root
        new_node_list: list[SearchNode] = []
        labels = np.argmax(u, axis=0)
        for i in range(n_clusters):
            child_list = []
            for j in range(len(labels)):
                if labels[j] == i:
                    child_list.append(node_list[j])
            if len(child_list) == 0:
                continue
            node_data = np.array(cnts[i])
            node_des = ""
            if self.summary:
                summary_model = OpenAi.OpenAi(url=settings.API_URL,
                                            api_key=settings.API_KEY,
                                            model=settings.TEXT_HANDLER,
                                            prompt=prompt.TEXT_PROMPT,
                                            temperature=0.1,)
                node_des = self.summary_chunk(child_list, summary_model)
                embedding = self.embedding_model.create_embedding(node_des)["data"][0]["embedding"]
                node_data = list(embedding)
            new_node = SearchNode(node_data)
            new_node.des = node_des
            new_node_list.append(new_node)
            new_node.child_list = child_list
        return self.init_search_tree_cmeans(new_node_list)
    
    def summary_chunk(self, node_list: list[SearchNode], summary_model: OpenAi.OpenAi):
        _prompt = "总结以下片段，相关的请一并总结，不相关的另起编号总结。总字数不超过300字：\n"
        for idx, node in enumerate(node_list):
            _prompt += "片段{}:\n{}\n\n".format(idx, node.des)
        summary_model.messages = []
        return summary_model(_prompt)
    
    def init(self):
        file_content = self.load_file()
        chunks = self.chunk_text(file_content)
        node_list: list[SearchNode] = []
        # 编码
        for idx, chunk in enumerate(chunks):
            embedding = self.embedding_model.create_embedding(chunk["des"])["data"][0]["embedding"]
            current_node = SearchNode(list(embedding))
            current_node.des = chunk["des"]
            current_node.start_line = chunk["start_line"]
            current_node.end_line = chunk["end_line"]
            node_list.append(current_node)
            yield json.dumps({"file_name": self.file_name, "step": 0,"idx": idx, "total": len(chunks)})
        
        # 保存
        if self.classification_alg == "cmeans":
            root = self.init_search_tree_cmeans(node_list)
        else:
            root = self.init_search_tree_kmeans(node_list)
        self.root = root
        self.rag_db.save_search_tree(root)
        yield json.dumps({"file_name": self.file_name, "step": 1, "idx": 0, "total": 0})
    
    def search(self, query: str):
        if self.root is None:
            self.root = self.rag_db.load_search_tree_with_name(self.file_name)
        if self.root is None:
            return None
        embedding = self.embedding_model.create_embedding(query)["data"][0]["embedding"]
        return self.rag_db.search_tree(self.root, embedding)
    
    def __del__(self):
        if self.embedding_model._sampler is not None:
            self.embedding_model._sampler.close()
        self.embedding_model.close()

class RAG:
    # 对于直接的链表搜索，这里采用向量数据库Chromadb
    def __init__(self, file_name):
        self.file_name = file_name
        self.file_path = os.path.join(settings.RAG_UPLOAD_PATH, file_name)
        self.client = chromadb.PersistentClient(path=settings.RAG_VECTOR_DATABASE_PATH)

        self.tokenizer = AutoTokenizer.from_pretrained(settings.RAG_TOKENIZER_PATH_OR_NAME)
        self.max_token = settings.RAG_N_CTX
        self.n_gpu_layer = settings.RAG_EMBEDDING_GPU_LAYER
        self.embedding_model = Llama(settings.RAG_EMBEDDING_MODEL,
                                     n_ctx=self.max_token,
                                     embedding=True,
                                     verbose=False,
                                     n_gpu_layers=self.n_gpu_layer)
        # 初始化后可用
        self.collection = None
    
    def get_file_type(self):
        # 目前只支持文本文件
        return "text"
    
    def load_file(self):
        file_type = self.get_file_type()
        if file_type == "text":
            with open(self.file_path, "rt", encoding="utf-8") as f:
                return f.read()
        else:
            return None
    
    def chunk_text(self, text: str):
        # 将文本分割为多个区块
        lines = text.split('\n')
        chunks = []
        current_chunk_token_num = 0
        current_chunk = {
            'start_line': 0,
            'end_line' : 0,
            'des': ""
        }
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            line_tokens = self.tokenizer.encode(line, add_special_tokens=False)
            if current_chunk_token_num + len(line_tokens) > self.max_token:
                current_chunk['end_line'] = idx
                current_chunk_tokens = self.tokenizer.encode(current_chunk["des"], add_special_tokens=False)
                current_chunk_tokens = current_chunk_tokens[-settings.RAG_OVERLAPPING_TOKEN:]
                overlapping_parts = self.tokenizer.decode(current_chunk_tokens)
                current_chunk_token_num = settings.RAG_OVERLAPPING_TOKEN + len(line_tokens)
                chunks.append(current_chunk)
                current_chunk = {
                    'start_line': idx,
                    'end_line' : idx,
                    'des': overlapping_parts + line
                }
            else:
                current_chunk["des"] += line + "\n"
                current_chunk_token_num += len(line_tokens)
            idx += 1
        return chunks
    
    def delete_file_data(self, file_name: str):
        # 删除文件数据
        collection = self.client.get_or_create_collection(
            name="rag_collection",
            metadata={"hnsw:space": "cosine"}
        )
        collection.delete(where={'file_name': file_name})
    
    def init(self):
        # 初始化数据库等，如果需要添加多个文件，直接更改当前对象的`file_name`属性并调用该函数
        # 同名数据视作更改，先删除原数据
        self.delete_file_data(self.file_name)
        file_content = self.load_file()
        model = self.embedding_model
        self.collection = self.client.get_or_create_collection(
            name="rag_collection",
            metadata={"hnsw:space": "cosine"}
        )
        chunks = self.chunk_text(file_content)
        for idx, chunk in enumerate(chunks):
            embedding = model.create_embedding(chunk["des"])["data"][0]["embedding"]
            self.collection.add(
                documents=[chunk["des"]],
                embeddings=[embedding],
                metadatas=[{"file_name":self.file_name, "start_line": chunk["start_line"], "end_line": chunk["end_line"]}],
                ids=[str(uuid.uuid4())]
            )
            yield json.dumps({"file_name": self.file_name, "idx": idx, "total": len(chunks)}) + "\n"
    
    def search(self, query: str, top_k: int = 4):
        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name="rag_collection",
                metadata={"hnsw:space": "cosine"}
            )
        embedding = self.embedding_model.create_embedding(query)["data"][0]["embedding"]
        # query_tokens = self.tokenizer.encode(query, add_special_tokens=False)
        # token_list = [self.tokenizer.decode(token) for token in query_tokens if token != 0]
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        return results

    def __del__(self):
        if self.embedding_model._sampler is not None:
            self.embedding_model._sampler.close()
        self.embedding_model.close() 
        