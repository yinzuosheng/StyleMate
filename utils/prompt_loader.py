from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def load_system_prompts():
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error("[load_system_prompts]Missing main_prompt_path")
        raise e

    try:
        with open(system_prompt_path, "r", encoding="utf-8") as prompt_file:
            return prompt_file.read()
    except Exception as e:
        logger.error(f"[load_system_prompts]Failed: {str(e)}")
        raise e


def load_rag_prompts():
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error("[load_rag_prompts]Missing rag_summarize_prompt_path")
        raise e

    try:
        with open(rag_prompt_path, "r", encoding="utf-8") as prompt_file:
            return prompt_file.read()
    except Exception as e:
        logger.error(f"[load_rag_prompts]Failed: {str(e)}")
        raise e


if __name__ == "__main__":
    print(load_system_prompts())
