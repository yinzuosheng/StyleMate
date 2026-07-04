from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf, rag_conf
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger

import os


class VectorStoreService:
    def __init__(self):
        self.vector_store = self._init_vector_store()
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def _init_vector_store(self):
        store_type = str(rag_conf.get("vector_store_type", "chroma")).lower()
        if store_type == "milvus":
            try:
                from langchain_community.vectorstores import Milvus
            except Exception as exc:
                raise ImportError(
                    "Milvus support requires pymilvus and langchain-milvus."
                ) from exc

            connection_args = {
                "host": rag_conf.get("milvus_host", "127.0.0.1"),
                "port": int(rag_conf.get("milvus_port", 19530)),
            }

            return Milvus(
                embedding_function=embed_model,
                collection_name=chroma_conf["collection_name"],
                connection_args=connection_args,
            )

        persist_dir = get_abs_path(chroma_conf["persist_directory"])
        return Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=persist_dir,
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_document(self):
        """
        Load text/pdf data from data path into vector store, with MD5 de-dup.
        """

        def check_md5_hex(md5_for_check: str):
            md5_path = get_abs_path(chroma_conf["md5_hex_store"])
            if not os.path.exists(md5_path):
                open(md5_path, "w", encoding="utf-8").close()
                return False

            with open(md5_path, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    if line.strip() == md5_for_check:
                        return True
            return False

        def save_md5_hex(md5_for_check: str):
            md5_path = get_abs_path(chroma_conf["md5_hex_store"])
            with open(md5_path, "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)
            if read_path.endswith("pdf"):
                return pdf_loader(read_path)
            return []

        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if not md5_hex:
                continue

            if check_md5_hex(md5_hex):
                logger.info(f"[KB]Skip already loaded: {path}")
                continue

            try:
                documents: list[Document] = get_file_documents(path)
                if not documents:
                    logger.warning(f"[KB]No valid content: {path}")
                    continue

                split_document: list[Document] = self.spliter.split_documents(documents)
                if not split_document:
                    logger.warning(f"[KB]No chunks after split: {path}")
                    continue

                self.vector_store.add_documents(split_document)
                save_md5_hex(md5_hex)
                logger.info(f"[KB]Loaded: {path}")
            except Exception as e:
                logger.error(f"[KB]Failed to load: {path}, {str(e)}", exc_info=True)
                continue


if __name__ == "__main__":
    vs = VectorStoreService()
    vs.load_document()
