# app/routes/actors.py
from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

bp = Blueprint("actors", __name__)

@bp.get("/top")
def top_actors():
    sql = text("""
        SELECT a.actor_id,
               CONCAT(a.first_name,' ',a.last_name) AS actor_name,
               COUNT(fa.film_id) AS film_count
        FROM actor a
        JOIN film_actor fa ON a.actor_id = fa.actor_id
        GROUP BY a.actor_id, actor_name
        ORDER BY film_count DESC, actor_name
        LIMIT 5
    """)
    with current_app.config["ENGINE"].begin() as conn:
        rows = conn.execute(sql).mappings().all()
    return jsonify(data=[dict(r) for r in rows])

@bp.get("/<int:actor_id>")
def actor_detail(actor_id: int):
    """Basic actor info + total films in their filmography."""
    sql = text("""
        SELECT a.actor_id,
               a.first_name,
               a.last_name,
               CONCAT(a.first_name,' ',a.last_name) AS actor_name,
               COUNT(fa.film_id) AS film_count
        FROM actor a
        LEFT JOIN film_actor fa ON a.actor_id = fa.actor_id
        WHERE a.actor_id = :actor_id
        GROUP BY a.actor_id, a.first_name, a.last_name
    """)
    with current_app.config["ENGINE"].begin() as conn:
        row = conn.execute(sql, {"actor_id": actor_id}).mappings().first()
    if not row:
        return jsonify(error="Not found"), 404
    return jsonify(data=dict(row))

@bp.get("/<int:actor_id>/top-films")
def top_films_by_actor(actor_id: int):
    """Top 5 films for a given actor by rental count."""
    sql = text("""
        SELECT 
            f.film_id,
            f.title,
            COUNT(r.rental_id) AS rental_count
        FROM film f
        JOIN film_actor fa ON f.film_id = fa.film_id
        JOIN inventory i ON f.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        WHERE fa.actor_id = :actor_id
        GROUP BY f.film_id, f.title
        ORDER BY rental_count DESC, f.title
        LIMIT 5
    """)
    with current_app.config["ENGINE"].begin() as conn:
        rows = conn.execute(sql, {"actor_id": actor_id}).mappings().all()
    return jsonify(data=[dict(r) for r in rows])
