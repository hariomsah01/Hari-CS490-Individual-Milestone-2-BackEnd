from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
bp = Blueprint("rentals", __name__)

@bp.post("/")
def rent():
    body = request.get_json(force=True)
    customer_id = int(body.get("customer_id"))
    film_id = int(body.get("film_id"))
    store_id = int(body.get("store_id", 1))
    with current_app.config["ENGINE"].begin() as conn:
        inv = conn.execute(text("""
            SELECT i.inventory_id
            FROM inventory i
            LEFT JOIN rental r ON r.inventory_id = i.inventory_id AND r.return_date IS NULL
            WHERE i.film_id = :fid AND i.store_id = :sid AND r.rental_id IS NULL
            LIMIT 1
        """), {"fid": film_id, "sid": store_id}).mappings().first()
        if not inv: return jsonify(error="No copies available"), 409
        ins = conn.execute(text("""
            INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id)
            VALUES (NOW(), :inv_id, :cid, 1)
        """), {"inv_id": inv["inventory_id"], "cid": customer_id})
        rid = ins.lastrowid
    return jsonify(data={"rental_id": rid}), 201

@bp.patch("/<int:rental_id>/return")
def mark_return(rental_id: int):
    with current_app.config["ENGINE"].begin() as conn:
        result = conn.execute(text("""
            UPDATE rental SET return_date = NOW()
            WHERE rental_id = :rid AND return_date IS NULL
        """), {"rid": rental_id})
        if result.rowcount == 0:
            return jsonify(error="Already returned or not found"), 404
    return jsonify(data={"rental_id": rental_id, "returned": True})
