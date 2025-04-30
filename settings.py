import os

os.environ["TZ"] = "UTC"

if os.environ.get("DEPLOY_ENV") not in ["staging", "production"]:
    try:
        from dotenv import load_dotenv

        print("Loading Local `.env` File")
        load_dotenv()
    except ImportError:
        raise ImportError(
            "Please install `dotenv` or manually set secrets manaually and comment this block"
        )

EVALUATION_MODE = False

# Pinecone Settings:
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME")
PINECONE_INDEX_HOST = os.environ.get("PINECONE_INDEX_HOST")

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
TWS_API_KEY = os.environ.get("TWS_API_KEY")

# GPT Models Namespaces
GPT4O = "gpt-4o"
GPT4O_MINI = "gpt-4o-mini"
GPT41 = "gpt-4.1"
GPT41_MINI = "gpt-4.1-mini"
GPT41_NANO = "gpt-4.1-nano"
O3_MINI = "o3-mini"
O3 = "o3"
O4_MINI = "o4-mini"
O1 = "o1"
O1_MINI = "o1-mini"

# Claude Models Namespaces
CLAUDE35SONNET = "claude-3-5-sonnet-latest"
CLAUDE37SONNET = "claude-3-7-sonnet-latest"
CLAUDE35HAIKU = "claude-3-5-haiku-latest"


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
VOYAGEAI_API_KEY = os.environ.get("VOYAGEAI_API_KEY")
SEED = 31337


BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
HOST = os.environ.get("HOST", "localhost")
DEFAULT_DB_NAME = "growisedata"

# Embedding Model Namespace
EMBED3SMALL = "text-embedding-3-small"
EMBED3LARGE = "text-embedding-3-large"
EMBED2ADA = "text-embedding-ada-002"

MAX_TOKEN_CONTEXT = 500
DELIMITERS = ["***", "'''", "^^^", "###"]
EMPTY_KNOWLEDGE_MESSAGE = (
    "No Group Knowledge, Initialized Knowledge before using this Endpoint"
)

SIMILARITY_TOP_K = 10

# Use Pinecone Recomended Value
CHUNK_SIZE = 1024
BATCH_SIZE = 64
POOL_THREADS = 16
CHUNK_OVERLAP = 128
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_RETRIES = 10
DEFAULT_TEMPERATURE = 0.1

# MongoDB Settings:
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "growisedata")
MCP_SSE_HOST = os.environ.get("MCP_HOST", "http://localhost:6969/sse")

DEPLOYED = os.environ.get("DEPLOY_ENV") in ["production"]

DEFAULT_HTML_TAGS = [
    "section",
    "article",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "span",
    "b",
    "i",
    "u",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "a",
    "img",
    "figcaption",
    "table",
    "caption",
    "tr",
    "th",
    "td",
]


ADDITIONAL_NODE_NAMESPACE = "additional_nodes_group_{group_id}"
