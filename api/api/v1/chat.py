from fastapi import APIRouter, Depends, File, HTTPException, UploadFile



from core import ratelimit

from core.deps import get_current_user

from schemas.auth_user import AuthUser

from schemas.chat import ChatRequest, ChatResponse, TranscribeResponse

from services.chat_service import process_chat

from services.roadmap_service import save_roadmap

from services.stt_service import transcribe_audio



router = APIRouter(prefix="/chat", tags=["Chat"])

# A few minutes of speech is well under this; bigger uploads are refused before reaching Whisper
MAX_AUDIO_BYTES = 10 * 1024 * 1024





@router.post("", response_model=None, dependencies=[Depends(ratelimit.limit("chat"))])

def chat(

    body: ChatRequest,

    user: AuthUser = Depends(get_current_user),

):

    result = process_chat(

        message=body.message,

        documents_held=body.documents_held,

        sub_city=body.sub_city,

        goal=body.goal,

        sector=body.sector or body.industry,

        industry=body.industry,

        conversation_history=body.conversation_history,

    )

    if result.get("roadmap"):

        save_roadmap(result["roadmap"], user=user)



    updated_history = result.pop("updated_history", [])

    return {

        "message": "success",

        "payload": {

            **ChatResponse(**result).model_dump(),

            "updated_history": updated_history,

        },

    }





@router.post("/transcribe", response_model=None, dependencies=[Depends(ratelimit.limit("transcribe"))])

def transcribe(

    file: UploadFile = File(...),

    _user: AuthUser = Depends(get_current_user),

):

    content = file.file.read(MAX_AUDIO_BYTES + 1)

    if len(content) > MAX_AUDIO_BYTES:

        raise HTTPException(status_code=413, detail="That recording is too long. Keep it under 10 MB.")

    result = transcribe_audio(content, filename=file.filename or "audio.webm")

    return {

        "message": "success",

        "payload": TranscribeResponse(

            text=result.get("text", ""),

            detected_language=result.get("detected_language", "unknown"),

        ).model_dump(),

    }


