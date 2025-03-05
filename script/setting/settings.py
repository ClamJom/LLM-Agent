# BASE_SETTINGS

SQLITE_DATABASE_PATH = "./data/database.db"

API_URL = "https://api.siliconflow.cn/v1"
API_KEY = "xxx"

# 默认聊天模型
DEFAULT_MODEL = "Qwen/Qwen2.5-32B-Instruct"
# 标题总结模型
TITLE_SUMMERIZER = "deepseek-ai/DeepSeek-V2.5"
# 图片处理模型
IMAGE_HANDLER = "Pro/Qwen/Qwen2-VL-7B-Instruct"
# 文本总结模型
TEXT_HANDLER = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
# 语音处理模型
VOICE_HANDLER = "FunAudioLLM/SenseVoiceSmall"

# 文件上传位置
UPLOAD_PATH = "./uploads"

# RAG_SETTINGS

# 单独使用一个SQLITE数据库，方便测试.....
RAG_SQLITE_DATABASE_PATH = "./data/rag.db"

# 使用本地 embedding 模型
RAG_EMBEDDING_MODEL = "./model/granite-embedding-278m-multilingual-Q4_K_M.gguf"

# 模型上下文大小，具体可以查阅使用的Embedding模型的上下文
RAG_N_CTX = 512

# 模型GPU加载层数
RAG_EMBEDDING_GPU_LAYER = 0

# RAG重叠Token设置
RAG_OVERLAPPING_TOKEN = 100

# 分词器，这里使用`Deepseek R1 Distill 1.5B`的分词器，使用其它影响不大，
# 只是为了确保上下文的大小不会超过Embedding模型的上下文
RAG_TOKENIZER_PATH_OR_NAME = "./model/DeepSeek-R1-Distill-Qwen-1.5B"

# RAG上传文件的文件路径
RAG_UPLOAD_PATH = UPLOAD_PATH + "/rag"

# 向量数据库存储地址
RAG_VECTOR_DATABASE_PATH = "./data/rag.chroma"

# RAG搜索树设置（待改进）

# 簇大小，即一个叶节点含有多少个相似的上下文，实际分类并不一定按照该配置分，而是根据该
# 配置计算得到最终需要分得的总类数，因此一个叶节点的上下文可能超过该数量
RAG_CLUSTER_SIZE = 5

# 分类算法，有K-Means与C-Means两种，默认为K-Means
RAG_CLSSIFICATION_ALG = "kmeans"

# 生成树时是否生成描述（描述使用文本总结模型生成）
RAG_INIT_TREE_WITH_DES = True