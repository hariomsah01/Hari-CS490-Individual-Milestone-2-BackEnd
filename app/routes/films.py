from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
bp = Blueprint("films", __name__)

@bp.get("/top")
def top():
    limit = int(request.args.get("limit", 5))
    sql = text("""
        SELECT f.film_id, f.title, COUNT(r.rental_id) AS times_rented
        FROM rental r
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        GROUP BY f.film_id, f.title
        ORDER BY times_rented DESC, f.title
        LIMIT :limit
    """)
    with current_app.config["ENGINE"].begin() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return jsonify(data=[dict(r) for r in rows])

@bp.get("/<int:film_id>")
def details(film_id: int):
    meta_sql = text("""
        SELECT f.film_id, f.title, f.description, f.release_year, f.rating,
               f.length, f.rental_rate, c.name AS category
        FROM film f
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        WHERE f.film_id = :id
    """)
    actors_sql = text("""
        SELECT a.actor_id, CONCAT(a.first_name,' ',a.last_name) AS actor_name
        FROM actor a JOIN film_actor fa ON a.actor_id = fa.actor_id
        WHERE fa.film_id = :id
        ORDER BY actor_name
    """)
    with current_app.config["ENGINE"].begin() as conn:
        film = conn.execute(meta_sql, {"id": film_id}).mappings().first()
        actors = conn.execute(actors_sql, {"id": film_id}).mappings().all()
    if not film: return jsonify(error="Not found"), 404
    film = dict(film); film["actors"] = [dict(a) for a in actors]
    return jsonify(data=film)

@bp.get("/search")
def search():
    q = request.args.get("q", ""); actor = request.args.get("actor", ""); category = request.args.get("category", "")
    page_size = max(1, min(100, int(request.args.get("pageSize", 10))))
    page = max(1, int(request.args.get("page", 1))); offset = (page-1) * page_size
    if actor:
        sql = text("""
            SELECT DISTINCT f.film_id, f.title
            FROM film f JOIN film_actor fa ON f.film_id = fa.film_id
            JOIN actor a ON a.actor_id = fa.actor_id
            WHERE CONCAT(a.first_name,' ',a.last_name) LIKE CONCAT('%', :actor, '%')
            ORDER BY f.title LIMIT :limit OFFSET :offset
        """)
        params = {"actor": actor, "limit": page_size, "offset": offset}
    elif category:
        sql = text("""
            SELECT f.film_id, f.title
            FROM film f JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category c ON c.category_id = fc.category_id
            WHERE c.name LIKE CONCAT('%', :cat, '%')
            ORDER BY f.title LIMIT :limit OFFSET :offset
        """)
        params = {"cat": category, "limit": page_size, "offset": offset}
    else:
        sql = text("""
            SELECT f.film_id, f.title
            FROM film f
            WHERE f.title LIKE CONCAT('%', :q, '%')
            ORDER BY f.title LIMIT :limit OFFSET :offset
        """)
        params = {"q": q, "limit": page_size, "offset": offset}
    with current_app.config["ENGINE"].begin() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return jsonify(data=[dict(r) for r in rows], pageSize=page_size, offset=offset)

@bp.get("/<int:film_id>/availability")
def availability(film_id: int):
    store_id = int(request.args.get("store_id", 1))
    sql = text("""
        SELECT i.inventory_id
        FROM inventory i
        LEFT JOIN rental r ON r.inventory_id = i.inventory_id AND r.return_date IS NULL
        WHERE i.film_id = :fid AND i.store_id = :sid AND r.rental_id IS NULL
        LIMIT 1
    """)
    with current_app.config["ENGINE"].begin() as conn:
        row = conn.execute(sql, {"fid": film_id, "sid": store_id}).mappings().first()
    return jsonify(data=(dict(row) if row else None))
