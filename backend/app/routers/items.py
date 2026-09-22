from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import supabase

router = APIRouter(prefix="/api/items", tags=["items"])


# --------------- Schemas ---------------

class ItemCreate(BaseModel):
    title: str
    description: str | None = None


class ItemOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    created_at: str


# --------------- Routes ---------------

@router.get("", response_model=list[ItemOut])
def list_items(current_user: dict = Depends(get_current_user)):
    """Protected: returns all items belonging to the logged-in user."""
    user_id: str = current_user.get("sub") or current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    result = (
        supabase.table("items")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreate, current_user: dict = Depends(get_current_user)):
    """Protected: creates a new item for the logged-in user."""
    user_id: str = current_user.get("sub") or current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    result = (
        supabase.table("items")
        .insert({"user_id": user_id, "title": body.title, "description": body.description})
        .execute()
    )
    return result.data[0]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: str, current_user: dict = Depends(get_current_user)):
    """Protected: deletes an item if it belongs to the logged-in user."""
    user_id: str = current_user.get("sub") or current_user.get("id")
    (
        supabase.table("items")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )
