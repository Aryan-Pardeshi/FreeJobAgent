import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("agent")

SYSTEM_PROMPT = """You are an expert career advisor and job placement specialist.

The user will provide their resume text. Your job is to:

1. **Analyse the resume** to extract:
   - Primary job title / role (e.g. "Data Scientist", "Software Engineer")
   - Related/broader job titles for a second search
   - Location preference and Country (infer from preferred or detected location). Note: The search tools accept a `country` argument (full English country name e.g. "India", "USA", "UK", "Germany") that you must infer from the preferred or detected location.
   - Experience level → map to: 1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director
   - Work type → map to: 1=On-site, 2=Remote, 3=Hybrid (default 2=Remote if unclear)
   - **CRITICAL**: If Work Type is Remote ("2"), the location argument must be an empty string `""` (remote search requires empty location, but still pass the inferred country).

2. **Search for jobs** by calling `search_jobs_tool` with extracted params (including `country`).
   Then call `search_jobs_broad_tool` with a broader/related title and `country`.

3. **Present results** in a clean format:
   🏢 **Job Title** at **Company**
   📍 Location | 💼 Work Type | 💰 Salary (if available)
   🔗 **[Apply Here](url)**
   🎯 Short match reason

4. **Provide 2-3 application tips** tailored to the candidate's resume.

Be concise and ensure every job has a clickable apply link.
"""


def _content_to_text(content) -> str:
    """Normalize agent message content (string or list of content blocks) to a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, str):
                blocks.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    blocks.append(item["text"])
                elif "text" in item:
                    blocks.append(item["text"])
                elif "content" in item:
                    blocks.append(str(item["content"]))
                else:
                    blocks.append(str(item))
            else:
                blocks.append(str(item))
        return "\n".join(blocks)
    return str(content) if content is not None else ""


def get_llm(model: str, api_key: str, base_url: str) -> ChatOpenAI:
    """Instantiate and return ChatOpenAI model instance."""
    if not model or not str(model).strip():
        raise ValueError("LLM model cannot be empty")
    if not api_key or not str(api_key).strip():
        raise ValueError("LLM API key cannot be empty")
    if not base_url or not str(base_url).strip():
        raise ValueError("LLM base URL cannot be empty")

    logger.info(f"Configuring ChatOpenAI with model: {model.strip()}")
    return ChatOpenAI(
        model=str(model).strip(),
        api_key=str(api_key).strip(),
        base_url=str(base_url).strip().rstrip("/"),
        temperature=0,
    )


async def _run_agent_async(
    resume_text: str,
    user_location: str,
    preferences: dict | None,
    model: str,
    api_key: str,
    base_url: str,
) -> str:
    llm = get_llm(model=model, api_key=api_key, base_url=base_url)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = MultiServerMCPClient(
        {
            "job_recommender": {
                "command": sys.executable,
                "args": ["mcp_server.py"],
                "transport": "stdio",
                "cwd": project_root,
            }
        }
    )

    try:
        tools = await client.get_tools()
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        raise RuntimeError(f"Could not start the job search service: {e}") from e

    agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)

    input_text = f"USER'S DETECTED IP LOCATION: {user_location}\n"
    if preferences:
        prefs = dict(preferences)
        is_remote = "Remote" in prefs.get("work_type", "")
        if is_remote:
            prefs["location"] = ""
            loc_desc = "(none - remote search, pass empty string)"
        else:
            loc_desc = prefs.get("location") or "(none)"

        input_text += (
            "\n--- MANUAL USER PREFERENCES (OVERRIDE RESUME IF NOT 'Detect Automatically') ---\n"
            f"- Preferred Work Type: {prefs.get('work_type', '')}\n"
            f"- Preferred Experience Level: {prefs.get('experience_level', '')}\n"
            f"- Preferred Location: {loc_desc}\n"
        )
    input_text += f"\nRESUME TEXT:\n{resume_text}"

    try:
        result = await agent.ainvoke({"messages": [("human", input_text)]})
        return _content_to_text(result["messages"][-1].content)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise RuntimeError(f"Failed to generate recommendations: {e}") from e


def run_agent(
    resume_text: str,
    user_location: str,
    preferences: dict | None,
    model: str,
    api_key: str,
    base_url: str,
) -> str:
    """Run job recommendation agent synchronously."""
    return asyncio.run(
        _run_agent_async(
            resume_text=resume_text,
            user_location=user_location,
            preferences=preferences,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    )
