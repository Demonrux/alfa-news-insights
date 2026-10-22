from __future__ import annotations

from .trace import Trace


class PipelineError(RuntimeError):
    """Прогон остановлен, причина записана в трейсе"""

    def __init__(self, message: str, trace: Trace, **details):
        """Сохраняет причину остановки, трейс и подробности для ответа API"""
        super().__init__(message)
        self.trace, self.details = trace, details


class NotRelevant(PipelineError):
    """Новость не касается бизнеса этой компании"""


class InsightRejected(PipelineError):
    """Карточка не прошла проверки и клиенту не показывается"""
