"""
API endpoints for symbol groups and user symbol preferences
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/symbol-groups")
def get_symbol_groups(db: Session = Depends(get_db)):
    """Get all symbol groups with their symbols"""
    cursor = db.connection().connection.cursor()
    
    # Get all groups
    cursor.execute("""
        SELECT id, name, display_name, description, icon, sort_order
        FROM symbol_groups
        ORDER BY sort_order
    """)
    
    groups = []
    for row in cursor.fetchall():
        group = {
            "id": row[0],
            "name": row[1],
            "display_name": row[2],
            "description": row[3],
            "icon": row[4],
            "sort_order": row[5],
            "symbols": []
        }
        
        # Get symbols for this group
        cursor.execute("""
            SELECT id, symbol, display_name, description, sort_order
            FROM symbols
            WHERE group_id = ? AND is_active = 1
            ORDER BY sort_order
        """, (group["id"],))
        
        for symbol_row in cursor.fetchall():
            group["symbols"].append({
                "id": symbol_row[0],
                "symbol": symbol_row[1],
                "display_name": symbol_row[2],
                "description": symbol_row[3],
                "sort_order": symbol_row[4]
            })
        
        groups.append(group)
    
    return {"symbol_groups": groups}


@router.get("/plans-detailed")
def get_plans_detailed(db: Session = Depends(get_db)):
    """Get all plans with detailed information including symbol limits and features"""
    cursor = db.connection().connection.cursor()
    
    cursor.execute("""
        SELECT id, name, description, price, interval, 
               symbol_limit, allowed_groups, features
        FROM plans
        ORDER BY price
    """)
    
    plans = []
    for row in cursor.fetchall():
        plan = {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "price": float(row[3]),
            "interval": row[4],  # Changed from billing_cycle to interval
            "symbol_limit": row[5],  # None means unlimited
            "allowed_groups": json.loads(row[6]) if row[6] else [],
            "features": json.loads(row[7]) if row[7] else []
        }
        plans.append(plan)
    
    return {"plans": plans}


@router.get("/user/symbol-preferences")
def get_user_symbol_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's symbol preferences"""
    cursor = db.connection().connection.cursor()
    
    cursor.execute("""
        SELECT 
            usp.id,
            usp.symbol_id,
            s.symbol,
            s.display_name,
            sg.name as group_name,
            sg.display_name as group_display_name,
            usp.is_active,
            usp.created_at
        FROM user_symbol_preferences usp
        JOIN symbols s ON usp.symbol_id = s.id
        JOIN symbol_groups sg ON s.group_id = sg.id
        WHERE usp.user_id = ? AND usp.is_active = 1
        ORDER BY sg.sort_order, s.sort_order
    """, (current_user.id,))
    
    preferences = []
    for row in cursor.fetchall():
        preferences.append({
            "id": row[0],
            "symbol_id": row[1],
            "symbol": row[2],
            "display_name": row[3],
            "group_name": row[4],
            "group_display_name": row[5],
            "is_active": bool(row[6]),
            "created_at": row[7]
        })
    
    return {"preferences": preferences}


@router.post("/user/symbol-preferences")
def save_user_symbol_preferences(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save user's symbol preferences
    Expected data: {"symbol_ids": [1, 2, 3], "plan_id": 1}
    """
    symbol_ids = data.get("symbol_ids", [])
    plan_id = data.get("plan_id")
    
    if not symbol_ids:
        raise HTTPException(status_code=400, detail="No symbols selected")
    
    if not plan_id:
        raise HTTPException(status_code=400, detail="Plan ID required")
    
    cursor = db.connection().connection.cursor()
    
    # Validate plan limits
    cursor.execute("SELECT symbol_limit FROM plans WHERE id = ?", (plan_id,))
    plan = cursor.fetchone()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    symbol_limit = plan[0]
    
    # Check if user exceeds limit (None = unlimited)
    if symbol_limit is not None and len(symbol_ids) > symbol_limit:
        raise HTTPException(
            status_code=400, 
            detail=f"Plan allows maximum {symbol_limit} symbol(s), but {len(symbol_ids)} were selected"
        )
    
    # Deactivate all current preferences
    cursor.execute("""
        UPDATE user_symbol_preferences 
        SET is_active = 0 
        WHERE user_id = ?
    """, (current_user.id,))
    
    # Insert or update preferences
    for symbol_id in symbol_ids:
        cursor.execute("""
            INSERT INTO user_symbol_preferences (user_id, symbol_id, is_active)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, symbol_id) 
            DO UPDATE SET is_active = 1, updated_at = CURRENT_TIMESTAMP
        """, (current_user.id, symbol_id))
    
    db.commit()
    
    return {
        "message": "Symbol preferences saved successfully",
        "count": len(symbol_ids)
    }


@router.delete("/user/symbol-preferences/{preference_id}")
def delete_symbol_preference(
    preference_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific symbol preference"""
    cursor = db.connection().connection.cursor()
    
    cursor.execute("""
        UPDATE user_symbol_preferences 
        SET is_active = 0 
        WHERE id = ? AND user_id = ?
    """, (preference_id, current_user.id))
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Preference not found")
    
    db.commit()
    
    return {"message": "Symbol preference removed successfully"}
