# app/routes/rentals.py
from flask import Blueprint, request, current_app, jsonify
from sqlalchemy import text
from datetime import datetime

bp = Blueprint("rentals", __name__)

STORE_ID = 1
STAFF_ID = 1  # or derive from session/user later


# POST /rentals  -> create a new rental
@bp.get("/availability/<int:film_id>")
def availability(film_id: int):
    """Return total copies and currently available copies for a film at a store."""
    store_id = int(request.args.get("store_id", 1))
    sql = text("""
        SELECT
          (SELECT COUNT(*) FROM inventory i
             WHERE i.film_id = :film_id AND i.store_id = :store_id) AS total_copies,
          (SELECT COUNT(*)
             FROM inventory i
            WHERE i.film_id = :film_id AND i.store_id = :store_id
              AND NOT EXISTS (
                 SELECT 1 FROM rental r
                  WHERE r.inventory_id = i.inventory_id
                    AND r.return_date IS NULL
              )
          ) AS available
    """)
    with current_app.config["ENGINE"].begin() as conn:
        row = conn.execute(sql, {"film_id": film_id, "store_id": store_id}).mappings().first()
    if not row:
        return jsonify(data={"total_copies": 0, "available": 0})
    return jsonify(data=dict(row))


@bp.post("")
def create_rental():
    """Create a rental for a customer if an inventory copy is available."""
    payload = request.get_json(force=True) or {}
    film_id = payload.get("film_id")
    customer_id = payload.get("customer_id")
    store_id = payload.get("store_id", 1)

    if not film_id or not customer_id:
        return jsonify(error="film_id and customer_id are required"), 400

    with current_app.config["ENGINE"].begin() as conn:
        # 1) Validate customer exists
        cust = conn.execute(
            text("SELECT 1 FROM customer WHERE customer_id = :cid"),
            {"cid": customer_id}
        ).scalar()
        if not cust:
            return jsonify(error="Customer not found"), 404

        # 2) Find an available inventory_id at this store for this film
        inv = conn.execute(text("""
            SELECT i.inventory_id
            FROM inventory i
            WHERE i.film_id = :film_id
              AND i.store_id = :store_id
              AND NOT EXISTS (
                  SELECT 1 FROM rental r
                  WHERE r.inventory_id = i.inventory_id
                    AND r.return_date IS NULL
              )
            LIMIT 1
        """), {"film_id": film_id, "store_id": store_id}).scalar()

        if not inv:
            return jsonify(error="No copies available"), 409

        # 3) Pick a staff member for the store (Sakila has 1 per store)
        staff_id = conn.execute(
            text("SELECT staff_id FROM staff WHERE store_id = :store_id LIMIT 1"),
            {"store_id": store_id}
        ).scalar()
        if not staff_id:
            return jsonify(error="No staff found for store"), 500

        # 4) Insert the rental
        res = conn.execute(text("""
            INSERT INTO rental (rental_date, inventory_id, customer_id, return_date, staff_id)
            VALUES (NOW(), :inv, :cid, NULL, :staff)
        """), {"inv": inv, "cid": customer_id, "staff": staff_id})

        rid = res.lastrowid

    return jsonify(data={"rental_id": int(rid), "inventory_id": int(inv)}), 201


@bp.patch("/<int:rental_id>/return")
def return_rental(rental_id: int):
    """
    Mark a rental as returned now (if not already).
    """
    sql = text("""
        UPDATE rental
        SET return_date = NOW(), last_update = NOW()
        WHERE rental_id = :rid AND return_date IS NULL
    """)
    with current_app.config["ENGINE"].begin() as conn:
        res = conn.execute(sql, {"rid": rental_id})
        if res.rowcount == 0:
            return jsonify(error="Already returned or not found"), 404
    return jsonify(ok=True, rental_id=rental_id, returned=True)
