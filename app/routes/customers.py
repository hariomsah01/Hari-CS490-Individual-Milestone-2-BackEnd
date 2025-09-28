from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
bp = Blueprint("customers", __name__)

@bp.get("/")
def list_customers():
    q = (request.args.get("q", "") or "").strip()
    cid_raw = (request.args.get("id", "") or "").strip()

    # paging
    page_size = max(1, min(100, int(request.args.get("pageSize", 10))))
    page = max(1, int(request.args.get("page", 1)))
    offset = (page - 1) * page_size

    # helpers
    def to_int_or_none(s):
        try:
            return int(s)
        except Exception:
            return None

    cid = to_int_or_none(cid_raw)
    q_int = to_int_or_none(q)
    like = f"%{q}%"

    with current_app.config["ENGINE"].begin() as conn:
        # 1) If explicit id=... is passed, search by exact ID only
        if cid is not None:
            sql = text("""
                SELECT customer_id, first_name, last_name, email, active
                FROM customer
                WHERE customer_id = :cid
                ORDER BY last_name, first_name
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(sql, {"cid": cid, "limit": page_size, "offset": offset}).mappings().all()

        # 2) Else if q is numeric, search by ID **or** by name containing q
        elif q_int is not None:
            sql = text("""
                SELECT customer_id, first_name, last_name, email, active
                FROM customer
                WHERE customer_id = :q_int
                   OR first_name LIKE :like
                   OR last_name  LIKE :like
                ORDER BY last_name, first_name
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(sql, {"q_int": q_int, "like": like, "limit": page_size, "offset": offset}).mappings().all()

        # 3) Otherwise, normal name search
        else:
            sql = text("""
                SELECT customer_id, first_name, last_name, email, active
                FROM customer
                WHERE first_name LIKE :like
                   OR last_name  LIKE :like
                ORDER BY last_name, first_name
                LIMIT :limit OFFSET :offset
            """)
            rows = conn.execute(sql, {"like": like, "limit": page_size, "offset": offset}).mappings().all()

    return jsonify(data=[dict(r) for r in rows], pageSize=page_size, offset=offset)


@bp.get("/<int:cid>")
def customer_detail(cid: int):
    meta_sql = text("""
        SELECT c.customer_id, c.first_name, c.last_name, c.email, c.active, s.store_id
        FROM customer c JOIN store s ON c.store_id = s.store_id
        WHERE c.customer_id = :cid
    """)
    rentals_sql = text("""
        SELECT r.rental_id, f.title, r.rental_date, r.return_date
        FROM rental r JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        WHERE r.customer_id = :cid
        ORDER BY r.rental_date DESC
        LIMIT 25
    """)
    with current_app.config["ENGINE"].begin() as conn:
        cust = conn.execute(meta_sql, {"cid": cid}).mappings().first()
        hist = conn.execute(rentals_sql, {"cid": cid}).mappings().all()
    if not cust: return jsonify(error="Not found"), 404
    data = dict(cust); data["rentals"] = [dict(r) for r in hist]
    return jsonify(data=data)


