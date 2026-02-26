from sqlalchemy import text
from sqlalchemy.orm import Session


def log_usage_event(
    db: Session,
    user_id: str,
    event_type: str,
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_cost_usd: float = 0.0,
) -> None:
    db.execute(
        text(
            """
            insert into usage_event (
                user_id, event_type, model, prompt_tokens, completion_tokens, total_cost_usd
            )
            values (:user_id, :event_type, :model, :prompt_tokens, :completion_tokens, :total_cost_usd)
            """
        ),
        {
            "user_id": user_id,
            "event_type": event_type,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_cost_usd": total_cost_usd,
        },
    )
