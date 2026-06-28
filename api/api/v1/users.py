from fastapi import APIRouter, HTTPException, status

from pydantic import BaseModel, EmailStr, Field



from auth.supabase_auth import is_auth_configured, register_user, sign_in_with_password

from schemas.users import UserCreate



router = APIRouter(prefix="/users", tags=["Users"])





class LoginBody(BaseModel):

    email: EmailStr

    password: str = Field(min_length=6)





@router.post("", status_code=status.HTTP_201_CREATED)

def add_new_user(user: UserCreate):

    if not is_auth_configured():

        raise HTTPException(

            status_code=503,

            detail="Supabase Auth is not configured",

        )

    try:

        created = register_user(user.email, user.password, user.fullname)

    except Exception as exc:

        msg = str(exc)

        if "already" in msg.lower() or "exists" in msg.lower():

            raise HTTPException(status_code=409, detail="User already exists") from exc

        raise HTTPException(status_code=400, detail=msg) from exc



    return {

        "message": "success",

        "payload": {"user": created},

    }





@router.post("/login")

def user_login(body: LoginBody):

    """Returns Supabase access_token (same shape as before for the web app)."""

    if not is_auth_configured():

        raise HTTPException(

            status_code=503,

            detail="Supabase Auth is not configured",

        )

    try:

        tokens = sign_in_with_password(body.email, body.password)

    except Exception:

        raise HTTPException(

            status_code=403,

            detail="Incorrect email or password",

        ) from None

    return tokens


