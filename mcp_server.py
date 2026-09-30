import logging
from fastmcp import FastMCP
from src.job_api import search_jobs, search_jobs_broad, SUPPORTED_SITES

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("mcp-job-recommender")

mcp = FastMCP("Job Recommender")


@mcp.tool()
def search_jobs_tool(
    job_title: str,
    location: str = "",
    experience_level: str = None,
    work_type: str = None,
    results_wanted: int = 10,
    country: str = "USA",
) -> list[dict]:
    """Search for jobs across LinkedIn, Indeed, and Google.

    Args:
        job_title: Job title or role to search for
        location: City, state, or country for job location
        experience_level: 1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director
        work_type: 1=On-site, 2=Remote, 3=Hybrid
        results_wanted: Max results per site (default 10)
        country: Full English country name, used for Indeed (e.g. "USA", "India", "UK", "Germany")
    """
    logger.info(
        f"search_jobs: title='{job_title}' location='{location}' "
        f"exp={experience_level} work={work_type} results={results_wanted} country='{country}'"
    )
    try:
        return search_jobs(
            job_title=job_title,
            location=location,
            experience_level=experience_level,
            work_type=work_type,
            results_wanted=results_wanted,
            country=country,
        )
    except Exception as e:
        logger.error(f"search_jobs failed: {e}")
        return []


@mcp.tool()
def search_jobs_broad_tool(
    job_title: str,
    location: str = "",
    results_wanted: int = 15,
    country: str = "USA",
) -> list[dict]:
    """Broader job search without experience/work-type filters.
    Use this for a second pass to find more opportunities.

    Args:
        job_title: Job title or role
        location: City, state, or country
        results_wanted: Max results (default 15)
        country: Full English country name, used for Indeed (e.g. "USA", "India", "UK", "Germany")
    """
    logger.info(
        f"search_broad: title='{job_title}' location='{location}' "
        f"results={results_wanted} country='{country}'"
    )
    try:
        return search_jobs_broad(
            job_title=job_title,
            location=location,
            results_wanted=results_wanted,
            country=country,
        )
    except Exception as e:
        logger.error(f"search_jobs_broad failed: {e}")
        return []


@mcp.tool()
def list_supported_sites() -> list[str]:
    """Returns the list of supported job board sites."""
    return SUPPORTED_SITES


if __name__ == "__main__":
    logger.info("Starting MCP Job Recommender server...")
    mcp.run()
