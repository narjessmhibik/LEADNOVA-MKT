from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, Token, UserResponse
from app.services.auth_service import hash_password, verify_password, create_access_token, decode_token
import uuid, os, sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

router = APIRouter()


async def get_current_user(authorization: str = Header(None), db: AsyncSession = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non authentifié")
    try:
        payload = decode_token(authorization.split(" ", 1)[1])
        email = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL  = os.getenv("BACKEND_URL",  "http://localhost:8000")


def _send_verification_email(to_email: str, to_name: str, token: str):
    """Envoie l'email de confirmation via Brevo."""
    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = os.getenv("BREVO_API_KEY", "")
        api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        verify_url = f"{BACKEND_URL}/auth/verify/{token}?redirect={FRONTEND_URL}"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:32px">
          <h2 style="color:#1e3a8a">Confirmez votre adresse email</h2>
          <p>Bonjour <strong>{to_name}</strong>,</p>
          <p>Merci de vous être inscrit sur <strong>LeadPilot</strong>. Cliquez sur le bouton ci-dessous pour activer votre compte :</p>
          <a href="{verify_url}"
             style="display:inline-block;margin:24px 0;padding:14px 28px;background:#3b82f6;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">
            Confirmer mon email
          </a>
          <p style="color:#6b7280;font-size:13px">Ce lien est valide 24h. Si vous n'avez pas créé de compte, ignorez cet email.</p>
        </div>
        """
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": to_name}],
            sender={"email": os.getenv("FROM_EMAIL", "narjessmhibik12@gmail.com"), "name": "LeadPilot"},
            subject="Confirmez votre adresse email — LeadPilot",
            html_content=html,
        )
        api.send_transac_email(send_smtp_email)
    except ApiException as e:
        pass  # non bloquant


@router.post("/register")
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    token = str(uuid.uuid4())
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_verified=True,
        verification_token=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "Compte créé — vous pouvez vous connecter", "email": data.email}


@router.get("/verify/{token}", response_class=HTMLResponse)
async def verify_email(token: str, redirect: str = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        return HTMLResponse("""
        <html><body style="font-family:Arial;text-align:center;padding:60px">
          <h2 style="color:#ef4444"> Lien invalide ou expiré</h2>
          <p>Ce lien de confirmation n'est pas valide.</p>
        </body></html>""", status_code=400)

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    dest = redirect or FRONTEND_URL
    return HTMLResponse(f"""
    <html><body style="font-family:Arial;text-align:center;padding:60px">
      <h2 style="color:#22c55e">Email confirmé !</h2>
      <p>Votre compte LeadPilot est maintenant actif.</p>
      <p>Redirection en cours...</p>
      <script>setTimeout(()=>window.location.href='{dest}',2000)</script>
    </body></html>""")


@router.post("/login")
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token, "token_type": "bearer",
        "full_name": user.full_name or "", "email": user.email,
    }


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"email": user.email, "full_name": user.full_name or ""}


@router.put("/me")
async def update_me(data: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.get("full_name") is not None:
        user.full_name = data["full_name"]
    await db.commit()
    return {"email": user.email, "full_name": user.full_name or ""}