from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import LLM_MODEL_GPT_4O_MINI, MAX_TOKENS

def split_text(
    source_text: str,
    model_name: str = LLM_MODEL_GPT_4O_MINI,
    chunk_size: int = MAX_TOKENS,
):
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name=model_name,
        chunk_size=chunk_size,
        chunk_overlap=0,
    )

    source_text_chunks = text_splitter.split_text(source_text)

    return source_text_chunks
