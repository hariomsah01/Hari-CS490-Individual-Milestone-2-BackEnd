from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
bp = Blueprint("customers", __name__)



@bp.get("/detail/<int:cid>")
def customer_detail(cid: int):
    meta_sql = text("""
        SELECT c.customer_id, c.first_name, c.last_name, c.email, c.active, s.store_id
        FROM customer c
        JOIN store s ON c.store_id = s.store_id
        WHERE c.customer_id = :cid
    """)

    rentals_sql = text("""
        SELECT
            r.rental_id,
            i.film_id,
            f.title,
            r.rental_date,
            r.return_date
        FROM rental r
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        WHERE r.customer_id = :cid
        ORDER BY r.rental_date DESC
        LIMIT 50
    """)

    with current_app.config["ENGINE"].begin() as conn:
        cust = conn.execute(meta_sql, {"cid": cid}).mappings().first()
        hist = conn.execute(rentals_sql, {"cid": cid}).mappings().all()

    if not cust:
        return jsonify(error="Not found"), 404

    data = dict(cust)
    data["rentals"] = [dict(r) for r in hist]
    return jsonify(data=data)

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

def _to_int_or_none(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(str(v).strip())
    except Exception:
        return None


@bp.post("")
def create_customer_no_slash():
    return create_customer()

@bp.post("/")
def create_customer():
    """
    Create a new customer.
    Optional: customer_id (manual id).
    Required: first_name, last_name.
    Optional: email.
    Ensures address_id and store_id exist before inserting.
    """
    body = request.get_json(force=True) or {}
    first = (body.get("first_name") or "").strip().upper()
    last  = (body.get("last_name")  or "").strip().upper()
    email = (body.get("email")      or "").strip()
    custom_id = _to_int_or_none(body.get("customer_id"))

    if not (first and last):
        return jsonify(error="first_name and last_name required"), 400
    if custom_id is not None and custom_id <= 0:
        return jsonify(error="customer_id must be a positive integer"), 400

    try:
        with current_app.config["ENGINE"].begin() as conn:
            # Ensure we have a valid store_id and address_id in this DB
            store_id = conn.execute(text("SELECT MIN(store_id) FROM store")).scalar()
            address_id = conn.execute(text("SELECT MIN(address_id) FROM address")).scalar()

            if store_id is None:
                return jsonify(error="No stores in DB; load Sakila data first."), 400
            if address_id is None:
                return jsonify(error="No addresses in DB; load Sakila data first."), 400

            if custom_id is not None:
                # explicit ID: check not taken
                exists = conn.execute(
                    text("SELECT 1 FROM customer WHERE customer_id = :cid LIMIT 1"),
                    {"cid": custom_id},
                ).first()
                if exists:
                    return jsonify(error=f"Customer with id {custom_id} already exists"), 409

                insert_sql = text("""
                    INSERT INTO customer
                        (customer_id, store_id, first_name, last_name, email,
                         address_id, active, create_date, last_update)
                    VALUES
                        (:cid, :store_id, :first, :last, :email, :address_id, 1, NOW(), NOW())
                """)
                conn.execute(insert_sql, {
                    "cid": custom_id,
                    "store_id": store_id,
                    "first": first,
                    "last": last,
                    "email": email,
                    "address_id": address_id
                })
                new_id = custom_id
            else:
                insert_sql = text("""
                    INSERT INTO customer
                        (store_id, first_name, last_name, email,
                         address_id, active, create_date, last_update)
                    VALUES
                        (:store_id, :first, :last, :email, :address_id, 1, NOW(), NOW())
                """)
                res = conn.execute(insert_sql, {
                    "store_id": store_id,
                    "first": first,
                    "last": last,
                    "email": email,
                    "address_id": address_id
                })
                new_id = res.lastrowid or conn.exec_driver_sql("SELECT LAST_INSERT_ID()").scalar()

        return jsonify(ok=True, id=new_id)

    except IntegrityError as e:
        # FK or unique/length issues, etc.
        return jsonify(error=f"Integrity error: {str(e.orig)}"), 400
    except Exception as e:
        # surface any unexpected backend error (so the UI shows the real cause)
        return jsonify(error=str(e)), 500



@bp.get("/<int:customer_id>")
def get_customer(customer_id: int):
    sql = text("""
        SELECT c.customer_id, c.first_name, c.last_name, c.email, c.active,
               c.address_id, c.store_id, c.create_date, c.last_update
        FROM customer c
        WHERE c.customer_id = :cid
    """)
    with current_app.config["ENGINE"].begin() as conn:
        row = conn.execute(sql, {"cid": customer_id}).mappings().first()
        if not row:
            return jsonify(error="Not found"), 404
    return jsonify(data=dict(row))


@bp.patch("/<int:customer_id>")
def update_customer(customer_id: int):
    body = request.get_json(force=True) or {}
    first = body.get("first_name")
    last  = body.get("last_name")
    email = body.get("email")
    active = body.get("active")

    sets = []
    params = {"cid": customer_id}
    if first is not None:
        sets.append("first_name = :first")
        params["first"] = first.strip().upper()
    if last is not None:
        sets.append("last_name = :last")
        params["last"] = last.strip().upper()
    if email is not None:
        sets.append("email = :email")
        params["email"] = email.strip()
    if active is not None:
        sets.append("active = :active")
        params["active"] = 1 if active else 0
    if not sets:
        return jsonify(error="Nothing to update"), 400

    sql = text(f"""
        UPDATE customer
        SET {", ".join(sets)}, last_update = NOW()
        WHERE customer_id = :cid
    """)
    with current_app.config["ENGINE"].begin() as conn:
        res = conn.execute(sql, params)
        if res.rowcount == 0:
            return jsonify(error="Not found"), 404
    return jsonify(ok=True)


@bp.delete("/<int:customer_id>")
def delete_customer(customer_id: int):
    """
    Deletes a customer. Will fail if FK constraints block it.
    For demo: hard-delete; in real app prefer soft-delete.
    """
    sql = text("DELETE FROM customer WHERE customer_id = :cid")
    with current_app.config["ENGINE"].begin() as conn:
        res = conn.execute(sql, {"cid": customer_id})
        if res.rowcount == 0:
            return jsonify(error="Not found"), 404
    return jsonify(ok=True)



@bp.get("/<int:customer_id>/open-rentals")
def customer_open_rentals(customer_id: int):
    sql = text("""
        SELECT r.rental_id, f.film_id, f.title, r.rental_date
        FROM rental r
        JOIN inventory i ON i.inventory_id = r.inventory_id
        JOIN film f ON f.film_id = i.film_id
        WHERE r.customer_id = :cid AND r.return_date IS NULL
        ORDER BY r.rental_date DESC
    """)
    with current_app.config["ENGINE"].begin() as conn:
        rows = conn.execute(sql, {"cid": customer_id}).mappings().all()
    return jsonify(data=[dict(r) for r in rows])


@bp.get("/basic/<int:customer_id>")
def get_customer_basic(customer_id: int):
    sql = text("""
        SELECT c.customer_id, c.first_name, c.last_name, c.email, c.active,
               c.address_id, c.store_id, c.create_date, c.last_update
        FROM customer c
        WHERE c.customer_id = :cid
    """)
    with current_app.config["ENGINE"].begin() as conn:
        row = conn.execute(sql, {"cid": customer_id}).mappings().first()
        if not row: return jsonify(error="Not found"), 404
    return jsonify(data=dict(row))
