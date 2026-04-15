from langchain_core.messages import SystemMessage

from langchain_nvidia_ai_endpoints import ChatNVIDIA

thinking_llm = ChatNVIDIA(model="nvidia/nemotron-3-super-120b-a12b", temperature=0.2, max_tokens=4096, top_p=0.95, api_key="***")
coding_llm = ChatNVIDIA(model="qwen/qwen3.5-397b-a17b", temperature=0.2, api_key="***")
