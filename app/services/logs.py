from app.supabase_client import supabase
from fastapi import Request

def log_action(action: str, filename: str, token: str, request: Request = None):
    try:
        supabase.table("logs").insert({
            "action": action,
            "filename": filename,
            "token": token,
            "ip": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent") if request else None
        }).execute()
    except Exception as e:
        print("Error enviando log:", e)