"""ALM Analytics Engine package."""

__all__ = [
    "ALMAnalyticsInput",
    "ALMAnalyticsResult",
    "compare_alm_analytics_results",
    "run_alm_analytics",
]


def __getattr__(name: str):
    if name == "ALMAnalyticsInput":
        from pk_alm.alm_analytics_engine.analytics_input import ALMAnalyticsInput

        return ALMAnalyticsInput
    if name == "ALMAnalyticsResult":
        from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

        return ALMAnalyticsResult
    if name in {"compare_alm_analytics_results", "run_alm_analytics"}:
        from pk_alm.alm_analytics_engine.engine import (
            compare_alm_analytics_results,
            run_alm_analytics,
        )

        return {
            "compare_alm_analytics_results": compare_alm_analytics_results,
            "run_alm_analytics": run_alm_analytics,
        }[name]
    raise AttributeError(name)
