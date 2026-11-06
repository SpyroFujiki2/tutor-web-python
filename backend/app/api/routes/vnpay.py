import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import get_session
from app.core.vnpay import VNPAYSettings, get_vnpay_settings, verified_query
from app.models import CashOrder, User
from app.models.enums import CashOrderStatus
from app.modules.finance.vnpay import apply_ipn, checkout
from app.schemas.domain import DepositInput

router = APIRouter(prefix='/payments/vnpay', tags=['vnpay'])
logger = logging.getLogger(__name__)
DB = Annotated[Session, Depends(get_session)]
Current = Annotated[User, Depends(get_current_user)]


def configured_settings() -> VNPAYSettings | None:
    try:
        return get_vnpay_settings()
    except ValueError:
        raise HTTPException(status_code=503, detail='Cấu hình VNPAY chưa hợp lệ') from None


def required_settings(settings: Annotated[VNPAYSettings | None, Depends(configured_settings)]) -> VNPAYSettings:
    if settings is None:
        raise HTTPException(status_code=503, detail='VNPAY sandbox chưa được cấu hình')
    return settings


Config = Annotated[VNPAYSettings, Depends(required_settings)]


class CheckoutInput(DepositInput):
    bank_code: str | None = Field(default=None, min_length=3, max_length=20, pattern=r'^[A-Z0-9_]+$')


class CheckoutResponse(BaseModel):
    order_id: UUID
    payment_url: str
    expires_at: datetime


@router.get('/status')
def status(settings: Annotated[VNPAYSettings | None, Depends(configured_settings)]):
    return {'enabled': settings is not None, 'sandbox': settings is None or 'sandbox.' in settings.payment_url}


@router.post('/checkout', response_model=CheckoutResponse)
def create_checkout(payload: CheckoutInput, request: Request, session: DB, user: Current, settings: Config):
    # Uvicorn must only trust proxy headers from explicitly configured proxy IPs.
    result = checkout(session, user.id, payload.request_id, payload.package_id, settings,
                      request.client.host if request.client else '127.0.0.1', payload.bank_code)
    response = CheckoutResponse.model_validate(result)
    session.commit()
    return response


@router.get('/ipn')
def ipn(request: Request, session: DB, settings: Config, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    params = verified_query(request.query_params.multi_items(), settings)
    if params is None:
        return {'RspCode': '97', 'Message': 'Invalid signature'}
    try:
        result = apply_ipn(session, params, settings)
        session.commit()
        return result
    except (SQLAlchemyError, ValueError, LookupError, PermissionError) as error:
        session.rollback()
        logger.error('VNPAY notification could not be applied (%s)', type(error).__name__)
        return {'RspCode': '99', 'Message': 'Unable to apply notification'}


@router.get('/return')
def payment_return(request: Request, session: DB, settings: Config, response: Response):
    """Display only. A browser redirect never credits the wallet."""
    response.headers['Cache-Control'] = 'no-store'
    params = verified_query(request.query_params.multi_items(), settings)
    if params is None:
        return {'signature_valid': False, 'payment_status': 'invalid', 'credited': False}
    try:
        identity = UUID(hex=params.get('vnp_TxnRef', ''))
    except ValueError:
        return {'signature_valid': True, 'payment_status': 'invalid', 'credited': False}
    order = session.get(CashOrder, identity)
    matches = bool(order and order.bank_info and order.bank_info.get('provider') == 'vnpay'
                   and order.bank_info.get('txn_ref') == params.get('vnp_TxnRef')
                   and params.get('vnp_Amount') == str(order.amount_vnd * 100))
    success = params.get('vnp_ResponseCode') == '00' and params.get('vnp_TransactionStatus') == '00'
    return {'signature_valid': True, 'payment_status': 'success' if success and matches else 'failed',
            'credited': bool(matches and order.status == CashOrderStatus.SUCCESS)}
