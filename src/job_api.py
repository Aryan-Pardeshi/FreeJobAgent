import pandas as pd
from jobspy import scrape_jobs

SUPPORTED_SITES = ["linkedin", "indeed", "google", "zip_recruiter", "glassdoor"]

# experience level (1-5) -> JobSpy job_type. Only "internship" maps cleanly;
# the other levels are left unfiltered and handled by the LLM's ranking.
EXPERIENCE_MAP = {
    "1": "internship",
}

# work type (1=On-site, 2=Remote, 3=Hybrid) -> JobSpy is_remote flag
WORK_TYPE_MAP = {
    "1": False,
    "2": True,
    "3": False,
}

# Fields handed to the LLM. Full descriptions are huge and blow the context window,
# so they are truncated to DESCRIPTION_CHARS.
KEEP_FIELDS = [
    "title", "company", "location", "job_url", "site", "is_remote", "job_type",
    "min_amount", "max_amount", "currency", "interval", "date_posted",
]
DESCRIPTION_CHARS = 400


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar -> python scalar
        return value.item()
    return value


def search_jobs(
    job_title: str,
    location: str = "",
    experience_level: str = None,
    work_type: str = None,
    site_name: list = None,
    results_wanted: int = 10,
    hours_old: int = 720,
    country: str = "USA",
) -> list[dict]:
    if site_name is None:
        site_name = ["linkedin", "indeed", "google"]

    kwargs = {
        "site_name": site_name,
        "search_term": job_title,
        "results_wanted": results_wanted,
        "hours_old": hours_old,
        "country_indeed": country,
    }
    # google ignores `location`; it reads the query string, so fold location in.
    if location:
        kwargs["location"] = location
        kwargs["google_search_term"] = f"{job_title} jobs near {location}"
    if experience_level in EXPERIENCE_MAP:
        kwargs["job_type"] = EXPERIENCE_MAP[experience_level]
    if work_type in WORK_TYPE_MAP:
        kwargs["is_remote"] = WORK_TYPE_MAP[work_type]

    try:
        jobs_df = scrape_jobs(**kwargs)
    except Exception as e:
        raise RuntimeError(f"JobSpy scrape failed: {e}") from e

    if jobs_df is None or jobs_df.empty:
        return []

    jobs = []
    for record in jobs_df.to_dict(orient="records"):
        job = {k: _clean(record.get(k)) for k in KEEP_FIELDS}
        description = record.get("description")
        if isinstance(description, str) and description:
            job["description"] = description[:DESCRIPTION_CHARS]
        jobs.append(job)
    return jobs


def search_jobs_broad(
    job_title: str,
    location: str = "",
    results_wanted: int = 15,
    country: str = "USA",
) -> list[dict]:
    return search_jobs(
        job_title=job_title,
        location=location,
        site_name=["linkedin", "indeed"],
        results_wanted=results_wanted,
        country=country,
    )


if __name__ == "__main__":
    for job in search_jobs("Software Engineer", "New York", "4", "1", results_wanted=3):
        print(job)
