# StyleMate — 衣橱智能助理 Agent

基于 LangChain ReAct Agent + ChromaDB RAG 构建的衣橱智能助理系统，面向尺码推荐、场景穿搭、面料洗护、衣橱管理等消费级场景，采用 Streamlit 构建全栈对话应用。

## 功能

- **尺码推荐** — 身高体重驱动的7级尺码匹配（S~5XL），支持斤/公斤自动换算与宽松/修身版型偏移
- **穿搭推荐** — 基于场景、风格、季节、色彩偏好的多维穿搭引擎
- **面料洗护** — RAG 检索增强的洗护与保养建议
- **出行穿搭** — 集成高德 IP 定位 + 天气预报 API 的天气感知推荐
- **用户画像** — 7维画像长期记忆（身高/体重/版型/风格/色彩/场景/体型），正则自动提取 + 冲突检测
- **Plan-SelfReflect** — 执行前 LLM 生成3-5步计划注入上下文，执行后自检模块校验完整性
- **LangGraph Middleware** — `@wrap_tool_call` / `@before_model` 全链路工具调用监控
- **用户系统** — 注册/登录（SHA-256 加盐哈希）、多会话对话记录持久化

## 快速开始

### 1. 安装依赖

```bash
cd cloth_ai
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 Key：

```env
DASHSCOPE_API_KEY=your-dashscope-key
AMAP_API_KEY=your-amap-key
```

### 3. 初始化知识库

```bash
python -c "from rag.vector_store import VectorStoreService; VectorStoreService().load_document()"
```

### 4. 启动应用

```bash
streamlit run app.py
```

浏览器打开 http://localhost:8501

## 技术栈

Python · LangChain · ChromaDB · Streamlit · LangGraph · 高德天气 API · DashScope (Qwen)

## 向量库切换

默认 ChromaDB，可在 `config/rag.yml` 中将 `vector_store_type` 改为 `milvus`。

## 项目结构

```
cloth_ai/
├── agent/            # ReAct Agent + 8工具
├── rag/              # ChromaDB 向量库 + RAG 检索链
├── model/            # LLM/Embedding 工厂
├── utils/            # 用户认证、对话存储、配置加载
├── config/           # YAML 配置文件
├── prompts/          # System prompt + RAG 模板
├── data/             # 知识库文本 + 用户数据
└── app.py            # Streamlit 入口
```
