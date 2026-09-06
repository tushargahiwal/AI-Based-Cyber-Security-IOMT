from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.report import ReportAuthor, ReportCreateRequest, ReportListResponse, ReportOut
from services import audit_service, export_service, report_service

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _to_out(report) -> ReportOut:
    out = ReportOut.model_validate(report, from_attributes=True)
    out.generated_by_username = report.author.username if report.author else None
    return out


@router.get("", response_model=ReportListResponse)
def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    report_type: str | None = Query(default=None),
    generated_by: int | None = Query(default=None, description="filter to one author"),
    patient_id: int | None = Query(default=None, description="only reports scoped to this patient"),
    created_from: datetime | None = Query(default=None, description="generated on or after"),
    created_to: datetime | None = Query(default=None, description="generated before"),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("reports.read")),
):
    items, total = report_service.list_reports(
        db, page=page, size=size, report_type=report_type, generated_by=generated_by,
        patient_id=patient_id, created_from=created_from, created_to=created_to,
    )
    return ReportListResponse(
        items=[_to_out(r) for r in items],
        total=total, page=page, size=size,
        authors=[ReportAuthor(**a) for a in report_service.list_authors(db)],
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_report(
    body: ReportCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("reports.generate")),
):
    report = report_service.generate(
        db,
        report_type=body.report_type,
        title=body.title,
        period_start=body.period_start,
        period_end=body.period_end,
        filters=body.scope_filters(),
        actor_user_id=ctx.user.id,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="GENERATE_REPORT",
        entity_type="report",
        entity_id=report.id,
        new_value={"report_type": report.report_type, "title": report.title,
                   "filters": report.filters},
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(report)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("reports.read")),
):
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return _to_out(report)


@router.get("/{report_id}/export")
def export_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("reports.read")),
):
    """Download the report as an .xlsx workbook.

    Reading a report and exporting the same report are the same disclosure, so
    this needs no permission beyond reports.read — but it is logged, because a
    spreadsheet of patient-linked alerts leaves the system and a compliance
    audit will want to know who took a copy.
    """
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")

    details = report_service.detail_rows(db, report)
    content = export_service.build_workbook(report, details)
    filename = export_service.filename_for(report)

    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="EXPORT_REPORT",
        entity_type="report",
        entity_id=report.id,
        new_value={"format": "xlsx", "rows": {k: len(v) for k, v in details.items()}},
        ip_address=request.client.host if request.client else None,
    )

    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            # filename* carries the UTF-8 form for clients that understand it;
            # the plain filename is the ASCII fallback.
            "Content-Disposition": f"attachment; filename=\"{filename}\"; "
                                   f"filename*=UTF-8''{quote(filename)}",
            "Content-Length": str(len(content)),
        },
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("reports.generate")),
):
    report_service.delete_report(db, report_id=report_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DELETE_REPORT",
        entity_type="report",
        entity_id=report_id,
        ip_address=request.client.host if request.client else None,
    )
