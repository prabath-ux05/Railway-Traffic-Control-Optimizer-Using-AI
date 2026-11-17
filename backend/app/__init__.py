"""
backend.app
~~~~~~~~~~~
Core application package exposing pipeline orchestration and execution services.
"""

from backend.app.main import app
from backend.app.pipeline import (
    PipelineExecutionResult,
    PipelineOrchestrator,
    run_pipeline,
)

__all__ = [
    "app",
    "PipelineExecutionResult",
    "PipelineOrchestrator",
    "run_pipeline",
]
