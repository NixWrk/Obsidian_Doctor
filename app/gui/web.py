from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.reporting.io import read_json
from app.reporting.pipeline import run_scan


def _open_file(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return

    subprocess.Popen(["xdg-open", str(path)])


def _load_report_payload(
    *,
    report_path: Path | None,
    vault_path: Path | None,
    config_path: Path | None,
    profile: str | None,
) -> dict[str, Any]:
    if report_path is not None:
        return read_json(report_path)

    if vault_path is None:
        raise ValueError("Either report_path or vault_path must be provided")

    report = run_scan(vault_path=vault_path, config_path=config_path, profile=profile)
    return report.to_dict()


def create_gui_app(report_payload: dict[str, Any]) -> FastAPI:
    app = FastAPI(title="Obsidian Doctor", version="0.1.0")

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

    app.state.report_payload = report_payload

    @app.get("/")
    def index(
        request: Request,
        category: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        q: str | None = Query(default=None),
    ):
        report = app.state.report_payload
        problems = list(report.get("problems", []))

        if category:
            problems = [problem for problem in problems if problem.get("category") == category]
        if severity:
            problems = [problem for problem in problems if problem.get("severity") == severity]
        if q:
            query = q.lower()
            problems = [
                problem
                for problem in problems
                if query in str(problem.get("title", "")).lower()
                or query in str(problem.get("description", "")).lower()
                or any(query in str(obj.get("path", "")).lower() for obj in problem.get("objects", []))
            ]

        categories = sorted({problem.get("category") for problem in report.get("problems", []) if problem.get("category")})
        severities = sorted({problem.get("severity") for problem in report.get("problems", []) if problem.get("severity")})

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "report": report,
                "summary": report.get("summary", {}),
                "problems": problems,
                "categories": categories,
                "severities": severities,
                "selected_category": category or "",
                "selected_severity": severity or "",
                "query": q or "",
            },
        )

    @app.get("/problem/{problem_id}")
    def problem_details(request: Request, problem_id: str):
        report = app.state.report_payload
        for problem in report.get("problems", []):
            if problem.get("id") == problem_id:
                return templates.TemplateResponse(
                    "details.html",
                    {
                        "request": request,
                        "report": report,
                        "problem": problem,
                    },
                )
        raise HTTPException(status_code=404, detail="Problem not found")

    @app.get("/open")
    def open_file(path: str, back: str = "/"):
        candidate = Path(path).expanduser().resolve()
        if not candidate.exists():
            raise HTTPException(status_code=404, detail="File does not exist")

        _open_file(candidate)
        return RedirectResponse(url=back, status_code=303)

    @app.get("/api/report")
    def api_report():
        return JSONResponse(content=app.state.report_payload)

    return app


def run_gui(
    *,
    report_path: Path | None,
    vault_path: Path | None,
    config_path: Path | None,
    profile: str | None,
    host: str,
    port: int,
) -> None:
    payload = _load_report_payload(
        report_path=report_path,
        vault_path=vault_path,
        config_path=config_path,
        profile=profile,
    )
    app = create_gui_app(payload)
    uvicorn.run(app, host=host, port=port)
