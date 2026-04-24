"""
Chinese text fixtures for RAG platform tests.

Contains sample Chinese documents in various domains (news, technical, mixed)
for testing Chinese text processing, segmentation, and retrieval.
"""

from typing import Dict, Any, List


CHINESE_NEWS_SAMPLE = """
中国人民银行今天宣布，将下调金融机构存款准备金率0.5个百分点，此举旨在支持实体经济发展，
促进经济平稳增长。这是今年以来第三次降准，预计将释放长期资金约1.2万亿元。

央行相关负责人表示，此次降准是稳健货币政策的延续，将继续保持流动性合理充裕，
降低企业融资成本。分析人士认为，这一政策将有效提振市场信心，推动经济复苏。

与此同时，央行还宣布将加大对科技创新、绿色发展等重点领域的支持力度，
推动金融资源更多流向实体经济薄弱环节。专家预计，未来货币政策将继续保持稳健基调，
根据经济形势变化适时适度进行预调微调。
"""

CHINESE_TECHNICAL_SAMPLE = """
机器学习是人工智能的一个分支，它使计算机系统能够从数据中自动学习和改进，
而无需进行明确的编程。机器学习算法使用历史数据作为输入来预测新的输出值。

推荐系统是机器学习最常见的应用之一。Netflix和YouTube等平台使用机器学习算法
来分析用户的观看历史，并推荐他们可能喜欢的其他内容。

机器学习的主要类型包括：

1. 监督学习：使用标记数据训练模型，如分类和回归问题
2. 无监督学习：从未标记数据中发现模式，如聚类和降维
3. 强化学习：通过与环境交互学习最优策略

深度学习是机器学习的一个子领域，使用多层神经网络处理复杂的数据模式。
卷积神经网络（CNN）擅长图像处理，循环神经网络（RNN）适合序列数据，
Transformer架构则在自然语言处理领域取得了突破性进展。
"""

CHINESE_MIXED_SAMPLE = """
我们使用Python和TensorFlow开发AI应用，主要技术栈包括：

**后端框架：**
- FastAPI：高性能异步API框架
- SQLAlchemy：ORM数据库操作
- Redis：缓存和消息队列

**机器学习：**
- TensorFlow 2.x：深度学习框架
- scikit-learn：传统机器学习算法
- Hugging Face Transformers：预训练模型

```python
from fastapi import FastAPI
from transformers import pipeline

app = FastAPI()
classifier = pipeline("sentiment-analysis")

@app.post("/analyze")
async def analyze_text(text: str):
    result = classifier(text)
    return {"sentiment": result[0]["label"]}
```

项目已部署在Kubernetes集群上，使用Docker容器化，支持水平扩展。
目前日处理请求量超过100万次，平均响应时间小于100毫秒。
"""

CHINESE_LONG_DOCUMENT = """
检索增强生成（Retrieval-Augmented Generation，简称RAG）是一种结合信息检索和文本生成的
人工智能技术架构。它通过在生成回答之前先从知识库中检索相关信息，从而提高生成内容的
准确性和可靠性。

RAG系统的工作流程可以分为以下几个关键步骤：

首先是文档索引阶段。系统会将知识库中的文档分割成适当大小的文本块，然后使用嵌入模型
将这些文本块转换为向量表示。这些向量随后被存储在向量数据库中，建立起高效的索引结构。
常用的嵌入模型包括OpenAI的text-embedding-ada-002和开源的sentence-transformers系列。

其次是查询处理阶段。当用户提出问题时，系统会使用相同的嵌入模型将问题转换为向量，
然后在向量数据库中进行相似度搜索，找出与问题最相关的若干文本块。这个过程通常被称为
语义检索或向量检索。

第三是上下文构建阶段。系统将检索到的相关文本块与用户的问题组合，形成一个完整的提示词
（prompt）。这个提示词会被发送给大语言模型，作为生成回答的上下文依据。

最后是答案生成阶段。大语言模型基于提供的上下文和问题，生成准确、相关的回答。
由于模型在生成时能够参考具体的知识内容，因此可以大大减少"幻觉"现象，提高回答的
可信度。

RAG技术的主要优势包括：

1. 知识可更新：与训练大型语言模型相比，更新知识库中的文档更加快速和经济。
   企业可以随时添加新的产品信息、政策更新等内容，无需重新训练模型。

2. 可追溯性：RAG系统可以提供信息来源，用户可以验证回答的准确性。
   这在医疗、法律、金融等需要高可靠性的领域尤为重要。

3. 降低成本：相比微调或训练大型语言模型，RAG的实现成本更低，
   特别适合中小型企业和创业公司。

4. 领域适应性强：通过构建特定领域的知识库，RAG系统可以快速适应
   各种专业领域的问答需求，如医疗诊断、法律咨询、技术支持等。

RAG系统的性能优化是实际应用中的关键挑战。以下是一些常用的优化策略：

在检索层面，可以采用混合检索策略，结合向量检索和关键词检索的优势。
向量检索擅长语义匹配，而关键词检索在精确匹配和专有名词检索方面表现更好。
将两种检索结果进行融合，可以显著提高召回率。

在重排序层面，可以使用专门的重排序模型对初步检索结果进行精细排序。
常用的重排序模型包括BGE Reranker、Cohere Rerank等，它们能够更准确地
评估查询与文档之间的相关性。

在生成层面，可以通过提示工程优化上下文的组织方式，帮助模型更好地利用
检索到的信息。例如，可以按照相关性排序展示文档，或者添加文档来源标识。

RAG技术的应用场景非常广泛。在企业知识管理领域，RAG可以帮助员工快速找到
公司内部的政策文档、技术规范和最佳实践。在客户服务领域，RAG驱动的智能客服
可以基于产品文档和FAQ库提供准确的回答。在教育和培训领域，RAG可以构建
智能学习助手，帮助学生理解复杂概念并找到相关学习资料。

随着大语言模型技术的不断发展，RAG架构也在持续演进。一些新的研究方向包括：
多模态RAG，支持图像、音频等多种模态的检索和生成；自适应RAG，根据问题复杂度
动态调整检索策略；以及知识图谱增强的RAG，将结构化知识融入检索过程。

总之，RAG技术为构建可靠、可扩展的智能问答系统提供了一条切实可行的技术路径。
它结合了检索系统的精确性和生成系统的灵活性，在众多实际应用场景中展现出
巨大的价值。随着技术的成熟和生态的完善，RAG将在更多领域发挥重要作用。
"""

CHINESE_QA_PAIRS = [
    {
        "question": "什么是RAG?",
        "answer": "RAG是检索增强生成（Retrieval-Augmented Generation）的缩写，是一种结合信息检索和文本生成的人工智能技术架构。它通过在生成回答之前先从知识库中检索相关信息，从而提高生成内容的准确性和可靠性。",
    },
    {
        "question": "RAG的主要优势是什么？",
        "answer": "RAG的主要优势包括：知识可更新、可追溯性、降低成本、领域适应性强。企业可以随时更新知识库而无需重新训练模型，系统可以提供信息来源供验证，实现成本比微调模型更低，可以快速适应各种专业领域。",
    },
    {
        "question": "机器学习有哪些主要类型？",
        "answer": "机器学习的主要类型包括：监督学习（使用标记数据训练模型）、无监督学习（从未标记数据中发现模式）、强化学习（通过与环境交互学习最优策略）。",
    },
    {
        "question": "什么是深度学习？",
        "answer": "深度学习是机器学习的一个子领域，使用多层神经网络处理复杂的数据模式。卷积神经网络（CNN）擅长图像处理，循环神经网络（RNN）适合序列数据，Transformer架构则在自然语言处理领域取得了突破性进展。",
    },
    {
        "question": "RAG系统的工作流程是什么？",
        "answer": "RAG系统的工作流程包括四个关键步骤：文档索引阶段（将文档转换为向量并存储）、查询处理阶段（将问题转换为向量并检索相关文档）、上下文构建阶段（组合检索结果与问题）、答案生成阶段（大语言模型基于上下文生成回答）。",
    },
]

CHINESE_SEARCH_QUERIES = [
    "RAG技术的应用场景有哪些？",
    "如何优化RAG系统的性能？",
    "向量数据库的选择标准是什么？",
    "什么是混合检索策略？",
    "大语言模型如何与RAG结合？",
]


def get_chinese_documents() -> List[Dict[str, Any]]:
    """Return list of Chinese sample documents for testing."""
    return [
        {
            "id": "doc-zh-001",
            "title": "央行降准新闻",
            "content": CHINESE_NEWS_SAMPLE.strip(),
            "metadata": {"language": "zh", "type": "news"},
        },
        {
            "id": "doc-zh-002",
            "title": "机器学习技术介绍",
            "content": CHINESE_TECHNICAL_SAMPLE.strip(),
            "metadata": {"language": "zh", "type": "technical"},
        },
        {
            "id": "doc-zh-003",
            "title": "AI项目技术栈",
            "content": CHINESE_MIXED_SAMPLE.strip(),
            "metadata": {"language": "zh", "type": "mixed"},
        },
    ]


def get_chinese_long_document() -> Dict[str, Any]:
    """Return long Chinese document for chunking tests."""
    return {
        "id": "doc-zh-long",
        "title": "RAG技术详解",
        "content": CHINESE_LONG_DOCUMENT.strip(),
        "metadata": {
            "language": "zh",
            "type": "long-form",
            "char_count": len(CHINESE_LONG_DOCUMENT),
        },
    }


def get_chinese_qa_pairs() -> List[Dict[str, str]]:
    """Return Chinese QA pairs for retrieval evaluation."""
    return CHINESE_QA_PAIRS


def get_chinese_search_queries() -> List[str]:
    """Return Chinese search queries for testing."""
    return CHINESE_SEARCH_QUERIES
