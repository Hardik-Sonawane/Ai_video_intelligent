"""
AI Agent core: LangChain ReAct agent supporting Google Gemini and Ollama.
Integrates RAG, tool calling, and agentic reasoning.
"""

import logging
from typing import Optional

# LangChain compatibility imports
try:
    from langchain.agents import AgentExecutor, create_react_agent
except ImportError:
    from langchain_community.agents import AgentExecutor, create_react_agent

try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate

try:
    from langchain_core.agents import AgentAction, AgentFinish
except ImportError:
    from langchain.schema import AgentAction, AgentFinish

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

from src.config import config
from src.tools.agent_tools import (
    ALL_TOOLS,
    init_tools,
)

logger = logging.getLogger(__name__)

# ── System Prompt ────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an AI Video Intelligence Agent. Your job is to answer questions about an uploaded video using the provided tools.

You have access to these tools:
{tools}

AVAILABLE TOOLS SUMMARY:
- search_transcript: Semantic RAG search in transcript (for content questions)
- get_transcript_at_timestamp: Get what was said at a specific time
- get_video_metadata: Get video technical details (duration, format, fps, etc.)
- get_full_transcript: Get the complete timestamped transcript
- analyze_video_frame: Visually analyze a frame at a specific timestamp
- summarize_video: Get a structured summary of video content
- generate_quiz: Create MCQ questions from the video
- find_topic_timestamp: Find when a topic is discussed
- extract_key_topics: Get key topics/segments from the video
- analyze_frame_range: Analyze multiple frames in a time range

INSTRUCTIONS:
1. Carefully read the user's question.
2. Determine which tool(s) are most appropriate.
3. Use tools to gather information — use multiple tools if needed.
4. Reason over the results carefully.
5. Provide a grounded, accurate answer with timestamps.

RULES:
- Always base your answer on actual video content retrieved by tools.
- Always include timestamps when referencing video content (e.g., [02:30]).
- For summarization questions → use summarize_video then get_full_transcript.
- For visual/appearance questions → use analyze_video_frame.
- For topic location questions → use find_topic_timestamp.
- For MCQ/quiz requests → use generate_quiz.
- For general content questions → use search_transcript.
- If you cannot find the information, say so honestly.
- Do NOT hallucinate or make up information.

FORMAT:
Use this exact format:

Question: the input question you must answer
Thought: Think about what tools you need and why
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have enough information to answer
Final Answer: Your comprehensive, grounded answer with timestamps

Begin!

Question: {input}
Thought:{agent_scratchpad}"""


class VideoAgent:
    """
    Main agent that orchestrates tools to answer questions about a video.
    Supports Google Gemini (via ChatGoogleGenerativeAI) and local Ollama models.
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or config.LLM_PROVIDER).lower()
        self.llm = None
        self._executor: Optional[AgentExecutor] = None
        self._langfuse = None
        self._init_error: Optional[str] = None

        self._setup_langfuse()
        self._setup_llm()
        if not self._init_error and self.llm is not None:
            self._build_agent()

    def _setup_langfuse(self):
        """Configure Langfuse tracing if credentials are available."""
        if config.LANGFUSE_ENABLED:
            try:
                from langfuse.callback import CallbackHandler
                self._langfuse = CallbackHandler(
                    secret_key=config.LANGFUSE_SECRET_KEY,
                    public_key=config.LANGFUSE_PUBLIC_KEY,
                    host=config.LANGFUSE_HOST,
                )
                logger.info("Langfuse tracing enabled")
            except ImportError:
                logger.warning("Langfuse package not installed, tracing disabled.")
        else:
            logger.info("Langfuse tracing disabled (no credentials set)")

    def _setup_llm(self):
        """Initialize the configured LLM backend."""
        try:
            if self.provider == "gemini":
                if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
                    self._init_error = (
                        "Gemini API key is not configured. "
                        "Please set GEMINI_API_KEY in .env or enter it in the sidebar."
                    )
                    logger.warning(self._init_error)
                    return

                if ChatGoogleGenerativeAI is None:
                    self._init_error = (
                        "langchain-google-genai package is not installed. "
                        "Run: pip install langchain-google-genai"
                    )
                    logger.error(self._init_error)
                    return

                self.llm = ChatGoogleGenerativeAI(
                    model=config.GEMINI_MODEL,
                    google_api_key=config.GEMINI_API_KEY,
                    temperature=0.1,
                    convert_system_message_to_human=True,
                )
                logger.info(f"Initialized Gemini LLM with model: {config.GEMINI_MODEL}")
            else:
                if ChatOllama is None:
                    self._init_error = (
                        "langchain-ollama package is not installed. "
                        "Run: pip install langchain-ollama"
                    )
                    logger.error(self._init_error)
                    return

                self.llm = ChatOllama(
                    model=config.OLLAMA_MODEL,
                    base_url=config.OLLAMA_BASE_URL,
                    temperature=0.1,
                    num_ctx=4096,
                )
                logger.info(f"Initialized Ollama LLM with model: {config.OLLAMA_MODEL}")
        except Exception as e:
            self._init_error = f"Failed to initialize LLM provider '{self.provider}': {str(e)}"
            logger.error(self._init_error, exc_info=True)

    def _build_agent(self):
        """Build the ReAct agent and executor."""
        if self.llm is None:
            return

        prompt = PromptTemplate.from_template(AGENT_SYSTEM_PROMPT)

        try:
            agent = create_react_agent(
                llm=self.llm,
                tools=ALL_TOOLS,
                prompt=prompt,
            )
        except Exception as e:
            self._init_error = f"Failed to create agent: {str(e)}"
            logger.error(self._init_error, exc_info=True)
            return

        callbacks = [self._langfuse] if self._langfuse else []

        self._executor = AgentExecutor(
            agent=agent,
            tools=ALL_TOOLS,
            verbose=True,
            max_iterations=10,
            max_execution_time=120,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            early_stopping_method="generate",
            callbacks=callbacks,
        )
        logger.info("Agent executor built successfully")

    def configure_video(
        self,
        vector_store,
        video_processor,
        video_metadata: dict,
        transcript_data: dict,
        frames_data: list,
    ):
        """
        Inject video-specific state into tools.
        Must be called before run() after each video upload.
        """
        init_tools(
            vector_store=vector_store,
            video_processor=video_processor,
            video_metadata=video_metadata,
            transcript_data=transcript_data,
            frames_data=frames_data,
            llm=self.llm,  # pass LLM for direct tool use (e.g. quiz generation)
        )
        logger.info(f"Agent configured for video: {video_metadata.get('video_id')}")

    def run(self, question: str) -> dict:
        """
        Run the agent with a user question.
        Returns dict with 'answer', 'steps', 'tools_used'.
        """
        if self._init_error:
            return {
                "answer": f"⚠️ Configuration Error: {self._init_error}",
                "steps": [],
                "tools_used": [],
            }

        if self._executor is None:
            return {
                "answer": "Agent is not initialized. Please check your provider settings.",
                "steps": [],
                "tools_used": [],
            }

        try:
            callbacks = [self._langfuse] if self._langfuse else []
            result = self._executor.invoke(
                {"input": question},
                config={"callbacks": callbacks},
            )

            answer = result.get("output", "No answer generated.")
            intermediate = result.get("intermediate_steps", [])

            # Extract steps for display
            steps = []
            tools_used = []
            for action, observation in intermediate:
                if isinstance(action, AgentAction):
                    steps.append({
                        "tool": action.tool,
                        "input": action.tool_input,
                        "observation": str(observation)[:800],
                    })
                    if action.tool not in tools_used:
                        tools_used.append(action.tool)

            return {
                "answer": answer,
                "steps": steps,
                "tools_used": tools_used,
            }

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            err_str = str(e)
            # Provide user-friendly error messages
            if "API_KEY" in err_str.upper() or "INVALID_ARGUMENT" in err_str.upper():
                friendly = "Invalid or missing API key. Please check your Gemini API key in the sidebar."
            elif "RESOURCE_EXHAUSTED" in err_str.upper() or "quota" in err_str.lower():
                friendly = "API quota exceeded. Please wait a moment and try again."
            elif "Connection" in err_str or "connect" in err_str.lower():
                friendly = f"Connection error: {err_str}. Check your network or Ollama server."
            else:
                friendly = f"I encountered an error while processing your question: {err_str}"

            return {
                "answer": friendly,
                "steps": [],
                "tools_used": [],
            }

    def check_gemini_connection(self) -> tuple[bool, str]:
        """Check if Gemini API key is configured and can connect."""
        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
            return False, "⚠️ Gemini API key not set (configure in .env or sidebar)"
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            # Lightweight verification: list models
            list(client.models.list(config={"page_size": 1}))
            return True, f"✅ Gemini connected | Model: {config.GEMINI_MODEL}"
        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg:
                return False, f"❌ Invalid Gemini API key: {err_msg[:80]}"
            return False, f"⚠️ Gemini check: {err_msg[:80]}"

    def check_ollama_connection(self) -> tuple[bool, str]:
        """Check if Ollama is running and the model is available."""
        import requests as req
        try:
            resp = req.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                model_available = any(
                    config.OLLAMA_MODEL.split(":")[0] in m for m in models
                )
                if model_available:
                    return True, f"✅ Ollama running | Model: {config.OLLAMA_MODEL}"
                else:
                    return False, (
                        f"⚠️ Ollama running but model '{config.OLLAMA_MODEL}' not found. "
                        f"Run: ollama pull {config.OLLAMA_MODEL}"
                    )
            return False, "⚠️ Ollama returned unexpected response."
        except req.exceptions.ConnectionError:
            return False, (
                "❌ Cannot connect to Ollama. "
                "Make sure Ollama is running: https://ollama.ai"
            )
        except Exception as e:
            return False, f"⚠️ Ollama check error: {str(e)[:80]}"

    def check_provider_connection(self) -> tuple[bool, str]:
        """Check connection for the currently selected provider."""
        if self.provider == "gemini":
            return self.check_gemini_connection()
        return self.check_ollama_connection()
