"""Routes for the management application."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.admin_auth import (
    authenticate_admin,
    create_admin_access_token,
    get_current_admin,
)
from core.database import get_db
from core.logging import get_logger
from db import models, repository, schemas
from services.excel_export_service import build_appointments_workbook

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = get_logger("api.admin")


def _service_to_admin_out(service: models.Service) -> schemas.ServiceAdminOut:
    return schemas.ServiceAdminOut(
        id=service.id,
        service_name=service.service_name,
        category_id=service.category_id,
        category_name=(
            service.category.category_name if service.category else None
        ),
        price=service.price,
        duration_minutes=service.duration_minutes,
        is_active=service.is_active,
        sort_order=service.sort_order,
    )


@router.post("/login", response_model=schemas.AdminToken)
def login(data: schemas.AdminLogin, db: Session = Depends(get_db)):
    admin = authenticate_admin(db, data.email, data.password)
    if not admin:
        logger.warning("管理員登入失敗: %s", data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
        )

    token = create_admin_access_token(admin.id)
    logger.info("管理員登入成功: admin_id=%s", admin.id)
    return schemas.AdminToken(access_token=token)


@router.get("/me", response_model=schemas.AdminOut)
def read_current_admin(admin: models.Admin = Depends(get_current_admin)):
    return admin


@router.get("/categories", response_model=List[schemas.Category])
def list_admin_categories(
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    return repository.get_categories(db)


@router.get("/services", response_model=List[schemas.ServiceAdminOut])
def list_admin_services(
    category_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    services = repository.list_admin_services(db, category_id=category_id)
    return [_service_to_admin_out(service) for service in services]


@router.post(
    "/services",
    response_model=schemas.ServiceAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_service(
    data: schemas.ServiceCreate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        service = repository.create_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.info(
        "管理員建立服務 admin_id=%s service_id=%s",
        admin.id,
        service.id,
    )
    return _service_to_admin_out(service)


@router.put("/services/reorder", response_model=List[schemas.ServiceAdminOut])
def reorder_admin_services(
    data: schemas.ServiceReorderRequest,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        services = repository.reorder_services(db, data.items)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.info(
        "管理員更新服務排序 admin_id=%s count=%s",
        admin.id,
        len(data.items),
    )
    return [_service_to_admin_out(service) for service in services]


@router.put("/services/{service_id}", response_model=schemas.ServiceAdminOut)
def update_admin_service(
    service_id: int,
    data: schemas.ServiceUpdate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        service = repository.update_service(db, service_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到服務")
    logger.info(
        "管理員更新服務 admin_id=%s service_id=%s",
        admin.id,
        service_id,
    )
    return _service_to_admin_out(service)


@router.delete("/services/{service_id}")
def delete_admin_service(
    service_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    result = repository.delete_service(db, service_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到服務")
    logger.info(
        "管理員刪除服務 admin_id=%s service_id=%s result=%s",
        admin.id,
        service_id,
        result,
    )
    if result == "disabled":
        return {
            "detail": "服務已有預約紀錄，已改為停用",
            "action": "disabled",
        }
    return {"detail": "服務已刪除", "action": "deleted"}


def _template_to_out(template: models.MessageTemplate) -> schemas.MessageTemplateOut:
    return schemas.MessageTemplateOut(
        id=template.id,
        key=template.key,
        name=template.name,
        category_id=template.category_id,
        category_name=(
            template.category.category_name if template.category else None
        ),
        body=template.body,
        description=template.description,
        is_active=template.is_active,
        updated_at=template.updated_at,
        created_at=template.created_at,
    )


@router.get("/message-templates", response_model=List[schemas.MessageTemplateOut])
def list_message_templates(
    key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    templates = repository.list_message_templates(db, key=key)
    return [_template_to_out(item) for item in templates]


@router.get(
    "/message-templates/{template_id}",
    response_model=schemas.MessageTemplateOut,
)
def get_message_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    template = repository.get_message_template_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到訊息範本")
    return _template_to_out(template)


@router.put(
    "/message-templates/{template_id}",
    response_model=schemas.MessageTemplateOut,
)
def update_message_template(
    template_id: int,
    data: schemas.MessageTemplateUpdate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        template = repository.update_message_template(db, template_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到訊息範本")
    logger.info(
        "管理員更新訊息範本 admin_id=%s template_id=%s key=%s",
        admin.id,
        template_id,
        template.key,
    )
    return _template_to_out(template)


@router.get("/business-settings", response_model=schemas.BusinessSettingsOut)
def get_admin_business_settings(
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    return repository.business_settings_to_out(db)


@router.put("/business-settings", response_model=schemas.BusinessSettingsOut)
def update_admin_business_settings(
    data: schemas.BusinessSettingsUpdate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        result = repository.update_business_settings(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.info("管理員更新營業設定 admin_id=%s", admin.id)
    return result


@router.post(
    "/business-holidays",
    response_model=schemas.BusinessHolidayOut,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_business_holiday(
    data: schemas.BusinessHolidayCreate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    try:
        holiday = repository.create_business_holiday(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.info(
        "管理員新增休假日 admin_id=%s date=%s",
        admin.id,
        holiday.holiday_date,
    )
    return holiday


@router.delete("/business-holidays/{holiday_id}")
def delete_admin_business_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    deleted = repository.delete_business_holiday(db, holiday_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到休假日")
    logger.info(
        "管理員刪除休假日 admin_id=%s holiday_id=%s",
        admin.id,
        holiday_id,
    )
    return {"detail": "休假日已刪除"}


@router.get("/stats", response_model=schemas.AdminStatsOut)
def get_admin_stats(
    period: str = Query(default="month", pattern="^(week|month|all)$"),
    db: Session = Depends(get_db),
    _: models.Admin = Depends(get_current_admin),
):
    return repository.get_admin_stats(db, period=period)


@router.post("/stats/appointments/export")
def export_admin_appointments(
    data: schemas.AppointmentExportRequest,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    rows = repository.list_admin_appointments_for_export(db, period=data.period)
    if data.appointment_ids is not None:
        id_set = set(data.appointment_ids)
        rows = [row for row in rows if row.id in id_set]
    stream = build_appointments_workbook(rows)
    filename = f"appointments_{data.period}.xlsx"
    logger.info(
        "管理員匯出預約明細 admin_id=%s period=%s rows=%s filtered=%s",
        admin.id,
        data.period,
        len(rows),
        data.appointment_ids is not None,
    )
    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
