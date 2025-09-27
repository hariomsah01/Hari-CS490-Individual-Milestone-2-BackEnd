from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

bp = Blueprint("actors", __name__)

@bp.get("/top")
def top_actors():
    """
    Top 5 actors by number of films in Sakila.
    """
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
