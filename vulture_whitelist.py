# vulture whitelist — false positives from FastMCP decorators and runtime-accessed attributes

# FastMCP registers tools/resources/prompts via decorators; the functions are
# looked up by the framework at runtime, not through direct module imports.

from anthropic_news_mcp.flags import FeatureFlags

# Pydantic / dataclass fields accessed via model_dump / model_copy
from anthropic_news_mcp.models import NewsItem
from anthropic_news_mcp.server import (
    build_digest_context,
    compare_updates,
    create_research_session,
    evaluate_claims,
    evidence_resource,
    generate_digest,
    get_recent_updates,
    get_research_session,
    get_source_health,
    get_timeline,
    get_update_detail,
    health_resource,
    latest_source_resource,
    latest_update_digest,
    list_sources,
    ping,
    research_session_brief,
    save_research_note,
    save_research_report,
    search_updates,
    search_web_sources,
    session_reports_resource,
    session_resource,
    session_timeline_resource,
    source_health_report,
    sources_resource,
    verify_claims_against_evidence,
    weekly_category_digest,
)

_ = ping
_ = list_sources
_ = get_recent_updates
_ = search_updates
_ = get_source_health
_ = get_update_detail
_ = search_web_sources
_ = get_timeline
_ = compare_updates
_ = build_digest_context
_ = create_research_session
_ = save_research_note
_ = save_research_report
_ = get_research_session
_ = evaluate_claims
_ = sources_resource
_ = health_resource
_ = latest_source_resource
_ = evidence_resource
_ = session_resource
_ = session_reports_resource
_ = session_timeline_resource
_ = latest_update_digest
_ = source_health_report
_ = weekly_category_digest
_ = generate_digest
_ = verify_claims_against_evidence
_ = research_session_brief
_ = NewsItem
_ = FeatureFlags
