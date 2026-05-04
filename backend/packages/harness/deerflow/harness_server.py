from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import asyncio
from deerflow.agents.evaluator.agent import EvaluatorAgent

app = FastAPI(title="DeerFlow OCHA Harness Server")

class Candidate(BaseModel):
    id: str
    name: str
    type: str
    category: Optional[str] = None
    features: List[str] = []

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global evaluator
    evaluator = EvaluatorAgent()
    print("--- OCHA Harness Server: Evaluator Agent initialized (Lifespan). ---")
    yield
    # Shutdown
    print("--- OCHA Harness Server: Shutting down. ---")

app = FastAPI(title="DeerFlow OCHA Harness Server", lifespan=lifespan)

@app.post("/evaluate")
async def evaluate_candidate(candidate: Candidate):
    if evaluator is None:
        raise HTTPException(status_code=503, detail="Evaluator not initialized")

    proposed_summary = (
        f"Manifest: {candidate.name}\n"
        f"Type: {candidate.type}\n"
        f"Features: {', '.join(candidate.features)}"
    )
    
    try:
        decision = await evaluator.evaluate(
            proposed_action=candidate.model_dump(),
            agent_thought="JS Bridge Request",
            state_summary=proposed_summary
        )
        
        # 强制归一化返回结果
        is_safe = str(decision.get("decision", "REJECTED")).upper() == "APPROVED"
        reason = decision.get("reasoning") or decision.get("reason") or "Audit decision rendered without explicit reasoning."
        
        return {
            "is_safe": is_safe,
            "score": 0.95 if is_safe else 0.1,
            "reason": reason,
            "suggested_actions": decision.get("suggested_actions") or []
        }
    except Exception as e:
        print(f"Server Evaluation Error: {str(e)}")
        return {
            "is_safe": False,
            "score": 0,
            "reason": f"OCHA System Error: {str(e)}"
        }

if __name__ == "__main__":
    # 默认监听 18789 端口，支持 JS Bridge 调用
    uvicorn.run(app, host="127.0.0.1", port=18789)
