from pydantic import BaseModel
from typing import Optional

class SessionConnectRequest(BaseModel):
    userId: str
    client_name: str
    provider_name: str
    contract_date: Optional[str] = None
    client_business_number: Optional[str] = None
    client_contact: Optional[str] = None
    provider_business_number: Optional[str] = None
    provider_contact: Optional[str] = None
