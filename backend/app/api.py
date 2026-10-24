"""HTTP entry point for the prompt and insight pipeline."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from llm.agent import InsightRejected, NotRelevant, PipelineError, Trace, run_insight_pipeline
from prompts.pe.domain.model import NotEligible
from prompts.pe.infra.llm import BudgetExceeded


app = FastAPI(title="Alfa News Insights API", version="0.1.0")
P1_CACHE: dict[str, dict] = {}


class CardRequest(BaseModel):
    company_data: dict[str, Any] = Field(description="Company row and optional group/counterparty context")
    news_item: dict[str, Any] = Field(description="News item with id, title, text, source and optional URL/date")
    role: str | None = None
    user_title: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/cards")
def create_card(body: CardRequest) -> dict[str, Any]:
    """Create one personalized insight card from company and news payloads."""
    trace = Trace()
    try:
        card = run_insight_pipeline(
            body.company_data,
            body.news_item,
            role=body.role,
            user_title=body.user_title,
            trace=trace,
            cache=P1_CACHE,
        )
    except NotEligible as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except NotRelevant as exc:
        return {"card": None, "reason": str(exc), "trace_id": trace.run_id, "trace": trace.summary()}
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (InsightRejected, PipelineError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": str(exc), "trace_id": trace.run_id, "issues": exc.details.get("issues", [])},
        ) from exc
    except RuntimeError as exc:
        # Covers transport/provider errors raised by the live model caller.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"card": card, "trace_id": trace.run_id, "trace": trace.summary()}
