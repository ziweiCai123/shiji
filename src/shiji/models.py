"""提取结果的数据模型;同时供 LLM 结构化输出的 schema 生成。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Technology(BaseModel):
    name: str = Field(description="技术/工具/概念名,例如 Docker、WSL2、git、React")
    what_learned: str = Field(description="今天关于它学到了/弄懂了什么,一句话")
    confidence: float = Field(
        ge=0.0, le=1.0, description="这是真实学到的把握程度,0 到 1"
    )


class Mistake(BaseModel):
    problem: str = Field(description="遇到的报错或卡住的问题")
    root_cause: str = Field(description="最终定位到的根因")
    resolved: bool = Field(description="这个问题今天是否解决了")


class DayExtraction(BaseModel):
    date: str = Field(description="YYYY-MM-DD")
    technologies: list[Technology] = Field(
        default_factory=list, description="今天接触/学到的技术"
    )
    questions_asked: list[str] = Field(
        default_factory=list, description="今天问出的有代表性的问题"
    )
    mistakes_and_debugging: list[Mistake] = Field(
        default_factory=list, description="今天踩的坑/调试/报错"
    )
    concepts_learned: list[str] = Field(
        default_factory=list, description="理解的概念(非具体工具)"
    )
    summary: str = Field(description="一句话总结今天的学习")
    struggle_level: str = Field(description="low / medium / high")


SCHEMA_JSON: dict = DayExtraction.model_json_schema()
